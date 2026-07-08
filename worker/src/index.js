// Cloudflare Worker API for flammel.cz orders.
// Endpoints:
//   POST /api/orders                     – create an order, check/decrement stock, e-mail confirmation
//   POST /api/orders/:orderNumber/cancel – cancel an order, restore stock, e-mail confirmation
//   GET  /api/stock?ids=a,b,c            – current quantities for tracked products (live display)
//
// Products with no row in product_stock are unlimited — no check, no display.
// Quantities are edited directly in the Cloudflare dashboard's D1 table view.

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = corsHeaders();

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: cors });
    }

    try {
      if (url.pathname === '/api/orders' && request.method === 'POST') {
        return await createOrder(request, env, cors);
      }
      const cancelMatch = url.pathname.match(/^\/api\/orders\/([^/]+)\/cancel$/);
      if (cancelMatch && request.method === 'POST') {
        return await cancelOrder(request, env, cors, decodeURIComponent(cancelMatch[1]));
      }
      if (url.pathname === '/api/stock' && request.method === 'GET') {
        return await getStock(request, env, cors);
      }
      return json({ error: 'not_found' }, 404, cors);
    } catch (err) {
      return json({ error: 'server_error', message: String(err && err.message || err) }, 500, cors);
    }
  },
};

function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

function json(data, status, cors) {
  return new Response(JSON.stringify(data), {
    status,
    headers: Object.assign({ 'Content-Type': 'application/json' }, cors),
  });
}

function generateOrderNumber() {
  const d = new Date();
  const pad = (n) => (n < 10 ? '0' : '') + n;
  const datePart = d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate());
  const rand = Math.floor(1000 + Math.random() * 9000);
  return 'FL-' + datePart + '-' + rand;
}

async function createOrder(request, env, cors) {
  const body = await request.json();

  if (!body.customer || !body.customer.name || !body.customer.email) {
    return json({ error: 'missing_customer_fields' }, 400, cors);
  }
  if (!Array.isArray(body.items) || body.items.length === 0) {
    return json({ error: 'empty_cart' }, 400, cors);
  }
  if (!body.delivery || !body.delivery.method || !body.payment || !body.payment.method) {
    return json({ error: 'missing_delivery_or_payment' }, 400, cors);
  }

  // Stock check first, before writing anything — reject the whole order if
  // any tracked (limited-quantity) item doesn't have enough left. Items with
  // no row in product_stock are unlimited and skip this check entirely.
  const trackedItems = [];
  for (const item of body.items) {
    const row = await env.DB.prepare('SELECT qty FROM product_stock WHERE product_id = ?').bind(item.id).first();
    if (row) {
      if (row.qty < item.qty) {
        return json(
          { error: 'insufficient_stock', productId: item.id, title: item.title, available: row.qty },
          409,
          cors
        );
      }
      trackedItems.push(item);
    }
  }

  const orderNumber = generateOrderNumber();
  const subtotal = body.items.reduce((sum, i) => sum + i.price * i.qty, 0);
  const shipping = Number(body.shippingPrice) || 0;
  const paymentFee = Number(body.paymentFee) || 0;
  const total = subtotal + shipping + paymentFee;

  const insert = await env.DB.prepare(
    `INSERT INTO orders (order_number, status, customer_name, customer_email, customer_phone,
       delivery_method, delivery_detail, billing_detail, payment_method, note,
       subtotal, shipping_price, payment_fee, total)
     VALUES (?, 'nova', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(
      orderNumber,
      body.customer.name,
      body.customer.email,
      body.customer.phone || '',
      body.delivery.method,
      body.delivery.detail || '',
      (body.billing && body.billing.detail) || 'Stejná jako dodací',
      body.payment.method,
      body.note || '',
      subtotal,
      shipping,
      paymentFee,
      total
    )
    .run();

  const orderId = insert.meta.last_row_id;
  const itemStmts = body.items.map((item) =>
    env.DB.prepare(
      `INSERT INTO order_items (order_id, product_id, title, price, qty) VALUES (?, ?, ?, ?, ?)`
    ).bind(orderId, item.id, item.title, item.price, item.qty)
  );
  const stockStmts = trackedItems.map((item) =>
    env.DB.prepare('UPDATE product_stock SET qty = qty - ? WHERE product_id = ? AND qty >= ?').bind(
      item.qty,
      item.id,
      item.qty
    )
  );
  await env.DB.batch([...itemStmts, ...stockStmts]);

  await sendOrderEmails(env, { orderNumber, body, subtotal, shipping, paymentFee, total });

  return json({ orderNumber, status: 'nova', total }, 200, cors);
}

async function cancelOrder(request, env, cors, orderNumber) {
  const body = await request.json().catch(() => ({}));
  const order = await env.DB.prepare('SELECT * FROM orders WHERE order_number = ?').bind(orderNumber).first();
  if (!order) return json({ error: 'not_found' }, 404, cors);
  if (body.email && String(order.customer_email).toLowerCase() !== String(body.email).toLowerCase()) {
    return json({ error: 'email_mismatch' }, 403, cors);
  }

  const { results: items } = await env.DB.prepare(
    'SELECT product_id, qty FROM order_items WHERE order_id = ?'
  ).bind(order.id).all();
  const restoreStmts = items.map((item) =>
    env.DB.prepare('UPDATE product_stock SET qty = qty + ? WHERE product_id = ?').bind(item.qty, item.product_id)
  );
  restoreStmts.push(
    env.DB.prepare("UPDATE orders SET status = 'zruseno' WHERE order_number = ?").bind(orderNumber)
  );
  await env.DB.batch(restoreStmts);

  await sendResendEmail(env, {
    to: order.customer_email,
    subject: `Zrušení objednávky ${orderNumber} – flammel.cz`,
    text: `Vaše objednávka č. ${orderNumber} byla podle vaší žádosti zrušena.`,
  });
  await sendResendEmail(env, {
    to: env.SHOP_NOTIFICATION_EMAIL,
    subject: `Zákazník zrušil objednávku ${orderNumber}`,
    text: `Objednávka č. ${orderNumber} (${order.customer_email}) byla zrušena zákazníkem.`,
  });

  return json({ orderNumber, status: 'zruseno' }, 200, cors);
}

async function getStock(request, env, cors) {
  const url = new URL(request.url);
  const ids = (url.searchParams.get('ids') || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  if (ids.length === 0) return json({}, 200, cors);

  const placeholders = ids.map(() => '?').join(',');
  const { results } = await env.DB.prepare(
    `SELECT product_id, qty, regular_price, sale_price FROM product_stock WHERE product_id IN (${placeholders})`
  )
    .bind(...ids)
    .all();

  const stock = {};
  for (const row of results) {
    stock[row.product_id] = {
      qty: row.qty,
      regularPrice: row.regular_price,
      salePrice: row.sale_price,
    };
  }
  return json(stock, 200, cors);
}

async function sendOrderEmails(env, { orderNumber, body, subtotal, shipping, paymentFee, total }) {
  const itemLines = body.items.map((i) => `- ${i.title} x${i.qty} = ${i.price * i.qty} Kč`).join('\n');

  const customerText = [
    `Děkujeme za objednávku č. ${orderNumber}!`,
    '',
    'Objednávka:',
    itemLines,
    '',
    `Mezisoučet: ${subtotal} Kč`,
    `Doprava: ${shipping} Kč`,
    `Platba: ${paymentFee} Kč`,
    `Celkem: ${total} Kč`,
    '',
    'Brzy se vám ozveme s dalšími informacemi.',
  ].join('\n');

  await sendResendEmail(env, {
    to: body.customer.email,
    subject: `Potvrzení objednávky ${orderNumber} – flammel.cz`,
    text: customerText,
  });

  const shopText = [
    `Nová objednávka ${orderNumber}`,
    `Jméno: ${body.customer.name}`,
    `E-mail: ${body.customer.email}`,
    `Telefon: ${body.customer.phone || '-'}`,
    `Doprava: ${body.delivery.method} — ${body.delivery.detail || ''}`,
    `Fakturace: ${(body.billing && body.billing.detail) || 'Stejná jako dodací'}`,
    `Platba: ${body.payment.method}`,
    `Poznámka: ${body.note || '-'}`,
    '',
    itemLines,
    '',
    `Celkem: ${total} Kč`,
  ].join('\n');

  await sendResendEmail(env, {
    to: env.SHOP_NOTIFICATION_EMAIL,
    subject: `Nová objednávka ${orderNumber}`,
    text: shopText,
  });
}

async function sendResendEmail(env, { to, subject, text }) {
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: env.MAIL_FROM,
      to: [to],
      subject,
      text,
    }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Resend error ${res.status}: ${detail}`);
  }
}
