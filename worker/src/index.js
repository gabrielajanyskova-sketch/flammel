// Cloudflare Worker API for flammel.cz orders.
// Endpoints:
//   POST /api/orders                     – create an order, check/decrement stock, e-mail confirmation
//                                           (+ low-stock alert to the shop when an item dips to ≤2 ks)
//   POST /api/orders/:orderNumber/cancel – cancel an order, restore stock, e-mail confirmation
//   GET  /api/stock?ids=a,b,c            – current quantities for tracked products (live display)
//   GET  /api/products                   – full product_stock table (read-only, public — the
//                                           static site generator pulls price/stock/category
//                                           from here at build time instead of Google Sheets)
//
// Products with no row in product_stock are unlimited — no check, no display.
// Everything here is edited directly in the Cloudflare dashboard's D1 table view.

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
      if (url.pathname === '/api/products' && request.method === 'GET') {
        return await getAllProducts(request, env, cors);
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

const SITE_URL = 'https://www.flammel.cz';
// Rendered from the site's actual Darloune logo font (assets/fonts/Darloune.otf)
// to a static image, since e-mail clients can't be relied on to load a
// custom @font-face — see scripts/generate_site.py's asset pipeline for how
// assets/img/logo-email.png was produced.
const LOGO_URL = `${SITE_URL}/assets/img/logo-email.png`;

function escapeHtml(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

// Shared branded wrapper (logo + brand colours) for every transactional
// e-mail — Resend just sends whatever HTML we hand it, there is no template
// editor on their side, so the look lives here in code.
function emailLayout(innerHtml) {
  return `<!doctype html>
<html lang="cs"><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#faf6ee;font-family:Georgia,'Times New Roman',serif;color:#4a4038;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#faf6ee;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" style="max-width:480px;background:#ffffff;border:1px solid #e7ddc9;border-radius:12px;overflow:hidden;">
        <tr><td align="center" style="background:#faf6ee;padding:24px;border-bottom:1px solid #e7ddc9;">
          <img src="${LOGO_URL}" width="180" height="51" alt="flammel" style="display:block;margin:0 auto;">
        </td></tr>
        <tr><td style="padding:28px 24px;font-size:15px;line-height:1.6;">
          ${innerHtml}
        </td></tr>
        <tr><td style="padding:16px 24px;background:#faf6ee;border-top:1px solid #e7ddc9;text-align:center;font-size:12px;color:#736858;">
          flammel.cz &middot; <a href="mailto:flammel@flammel.cz" style="color:#7d631c;">flammel@flammel.cz</a>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>`;
}

function itemRowsHtml(items) {
  return items.map((i) => (
    `<tr>
      <td style="padding:6px 0;border-bottom:1px solid #e7ddc9;">${escapeHtml(i.title)} &times; ${i.qty}</td>
      <td style="padding:6px 0;border-bottom:1px solid #e7ddc9;text-align:right;white-space:nowrap;">${i.price * i.qty} Kč</td>
    </tr>`
  )).join('');
}

function totalsRowsHtml(rows) {
  return rows.map(([label, value]) => (
    `<tr><td style="padding:3px 0;">${label}</td><td style="padding:3px 0;text-align:right;">${value}</td></tr>`
  )).join('');
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
      trackedItems.push({ ...item, qtyBefore: row.qty });
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
  await sendLowStockAlerts(env, trackedItems);

  return json({ orderNumber, status: 'nova', total }, 200, cors);
}

// Only e-mails once per item per dip below the threshold — an order that
// takes qty from, say, 5 straight to 0 still only crosses the line once,
// and once it's at/under the threshold every further order of that item is
// already blocked by the stock check above, so it can't re-fire.
const LOW_STOCK_THRESHOLD = 2;

async function sendLowStockAlerts(env, trackedItems) {
  for (const item of trackedItems) {
    const qtyAfter = item.qtyBefore - item.qty;
    if (item.qtyBefore > LOW_STOCK_THRESHOLD && qtyAfter <= LOW_STOCK_THRESHOLD) {
      await sendResendEmail(env, {
        to: env.SHOP_NOTIFICATION_EMAIL,
        subject: `Dochází sklad: ${item.title}`,
        text: `Produkt "${item.title}" (ID ${item.id}) má skladem už jen ${qtyAfter} ks. Zvažte doplnění zásob.`,
      });
    }
  }
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

async function getAllProducts(request, env, cors) {
  const { results } = await env.DB.prepare(
    'SELECT product_id, title, qty, regular_price, sale_price, category_slug FROM product_stock'
  ).all();

  const products = {};
  for (const row of results) {
    products[row.product_id] = {
      title: row.title,
      qty: row.qty,
      regularPrice: row.regular_price,
      salePrice: row.sale_price,
      categorySlug: row.category_slug,
    };
  }
  return json(products, 200, cors);
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

  const customerHtml = emailLayout(`
    <p style="margin:0 0 16px;font-size:17px;color:#211c17;">Děkujeme za objednávku č. <strong>${escapeHtml(orderNumber)}</strong>!</p>
    <table role="presentation" width="100%" style="border-collapse:collapse;font-size:14px;">${itemRowsHtml(body.items)}</table>
    <table role="presentation" width="100%" style="border-collapse:collapse;font-size:14px;margin-top:12px;">
      ${totalsRowsHtml([['Mezisoučet', `${subtotal} Kč`], ['Doprava', `${shipping} Kč`], ['Platba', `${paymentFee} Kč`]])}
    </table>
    <table role="presentation" width="100%" style="border-collapse:collapse;margin-top:10px;background:#faf6ee;border-radius:8px;">
      <tr><td style="padding:10px 14px;font-weight:bold;color:#211c17;">Celkem</td><td style="padding:10px 14px;text-align:right;font-weight:bold;color:#7d631c;font-size:17px;">${total} Kč</td></tr>
    </table>
    <p style="margin:20px 0 0;">Brzy se vám ozveme s dalšími informacemi.</p>
  `);

  await sendResendEmail(env, {
    to: body.customer.email,
    subject: `Potvrzení objednávky ${orderNumber} – flammel.cz`,
    text: customerText,
    html: customerHtml,
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

  const shopHtml = emailLayout(`
    <p style="margin:0 0 16px;font-size:17px;color:#211c17;">Nová objednávka <strong>${escapeHtml(orderNumber)}</strong></p>
    <table role="presentation" width="100%" style="border-collapse:collapse;font-size:14px;margin-bottom:16px;">
      ${totalsRowsHtml([
        ['Jméno', escapeHtml(body.customer.name)],
        ['E-mail', escapeHtml(body.customer.email)],
        ['Telefon', escapeHtml(body.customer.phone || '-')],
        ['Doprava', `${escapeHtml(body.delivery.method)} — ${escapeHtml(body.delivery.detail || '')}`],
        ['Fakturace', escapeHtml((body.billing && body.billing.detail) || 'Stejná jako dodací')],
        ['Platba', escapeHtml(body.payment.method)],
        ['Poznámka', escapeHtml(body.note || '-')],
      ])}
    </table>
    <table role="presentation" width="100%" style="border-collapse:collapse;font-size:14px;">${itemRowsHtml(body.items)}</table>
    <table role="presentation" width="100%" style="border-collapse:collapse;margin-top:10px;background:#faf6ee;border-radius:8px;">
      <tr><td style="padding:10px 14px;font-weight:bold;color:#211c17;">Celkem</td><td style="padding:10px 14px;text-align:right;font-weight:bold;color:#7d631c;font-size:17px;">${total} Kč</td></tr>
    </table>
  `);

  await sendResendEmail(env, {
    to: env.SHOP_NOTIFICATION_EMAIL,
    subject: `Nová objednávka ${orderNumber}`,
    text: shopText,
    html: shopHtml,
  });
}

async function sendResendEmail(env, { to, subject, text, html }) {
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
      html: html || emailLayout(`<p style="margin:0;white-space:pre-line;">${escapeHtml(text)}</p>`),
    }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Resend error ${res.status}: ${detail}`);
  }
}
