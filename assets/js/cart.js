// Client-side shopping cart backed by localStorage.
// There is no backend or payment gateway behind this static site, so the
// "checkout" step below sends the order straight to Web3Forms (which e-mails
// it to flammel@flammel.cz) instead of charging a card — see the notice on
// pokladna.html.
(function () {
  var STORAGE_KEY = 'flammel_cart';
  var PACKETA_API_KEY = 'b8b56c3f9361b7175d2bd60f70b40c7a';
  var WEB3FORMS_ACCESS_KEY = 'e7fbbc6f-f4d1-4485-a88a-0165a3875c0d';

  function getCart() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    } catch (e) {
      return [];
    }
  }

  function saveCart(cart) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cart));
    renderBadge();
  }

  function addToCart(item, qty) {
    var cart = getCart();
    var existing = cart.find(function (i) { return i.id === item.id; });
    if (existing) {
      existing.qty += qty;
    } else {
      cart.push(Object.assign({}, item, { qty: qty }));
    }
    saveCart(cart);
  }

  function removeFromCart(id) {
    saveCart(getCart().filter(function (i) { return i.id !== id; }));
  }

  function updateQty(id, qty) {
    var cart = getCart();
    var item = cart.find(function (i) { return i.id === id; });
    if (!item) return;
    item.qty = Math.max(1, qty);
    saveCart(cart);
  }

  function generateOrderNumber() {
    var d = new Date();
    var pad = function (n) { return (n < 10 ? '0' : '') + n; };
    var datePart = d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate());
    var rand = Math.floor(1000 + Math.random() * 9000);
    return 'FL-' + datePart + '-' + rand;
  }

  function cartCount(cart) {
    return cart.reduce(function (sum, i) { return sum + i.qty; }, 0);
  }

  function cartTotal(cart) {
    return cart.reduce(function (sum, i) { return sum + i.qty * i.price; }, 0);
  }

  function formatPrice(value) {
    return Math.round(value).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ' Kč';
  }

  var DELIVERY_LABELS = {
    zasilkovna_adresa: 'Zásilkovna – doručení na adresu',
    zasilkovna_vydejni: 'Zásilkovna – výdejní místo',
    zasilkovna_zbox: 'Zásilkovna – Z-BOX',
    ceska_posta: 'Česká pošta',
    osobni: 'Osobní vyzvednutí',
  };
  var SHIPPING_PRICES = {
    zasilkovna_adresa: 89,
    zasilkovna_vydejni: 69,
    zasilkovna_zbox: 65,
    ceska_posta: 99,
    osobni: 0,
  };
  var PAYMENT_LABELS = {
    online: 'Online platba kartou / Google Pay',
    prevodem: 'Platba předem na účet',
  };
  var PAYMENT_SURCHARGE = {
    online: 0,
    prevodem: 0,
  };

  function selectedDelivery(form) {
    var checked = form.querySelector('input[name="delivery"]:checked');
    return checked ? checked.value : 'zasilkovna_adresa';
  }
  function selectedPayment(form) {
    var checked = form.querySelector('input[name="payment"]:checked');
    return checked ? checked.value : 'online';
  }

  var FREE_SHIPPING_THRESHOLD = 2500;

  function shippingCostFor(delivery, subtotal) {
    if (subtotal >= FREE_SHIPPING_THRESHOLD) return 0;
    return SHIPPING_PRICES[delivery] || 0;
  }

  function renderFreeShippingBanner(subtotal) {
    var root = document.getElementById('free-shipping-banner');
    if (!root) return;
    var remaining = FREE_SHIPPING_THRESHOLD - subtotal;
    var pct = Math.max(0, Math.min(100, (subtotal / FREE_SHIPPING_THRESHOLD) * 100));
    var text = remaining <= 0
      ? 'Máte dopravu zdarma! ✨'
      : 'Ještě ' + formatPrice(remaining) + ' a máte dopravu zdarma!';
    root.innerHTML =
      '<div class="shipping-banner">' +
      '<div class="shipping-banner-text">' + text + '</div>' +
      '<div class="shipping-progress"><div class="shipping-progress-fill" style="width:' + pct + '%"></div></div>' +
      '</div>';
  }

  function setupCheckoutOptions() {
    var form = document.getElementById('checkout-form');
    if (!form) return;
    var addressFields = document.getElementById('address-fields');
    var pickupField = document.getElementById('pickup-point-field');
    var osobniNote = document.getElementById('osobni-note');
    var street = document.getElementById('street');
    var city = document.getElementById('city');
    var zip = document.getElementById('zip');
    var pickupInput = document.getElementById('pickup_point');

    function update() {
      var checked = form.querySelector('input[name="delivery"]:checked');
      var value = checked ? checked.value : 'zasilkovna_adresa';
      var isPickup = value === 'zasilkovna_vydejni' || value === 'zasilkovna_zbox';
      var isPersonal = value === 'osobni';
      addressFields.style.display = (isPickup || isPersonal) ? 'none' : '';
      pickupField.style.display = isPickup ? 'block' : 'none';
      osobniNote.style.display = isPersonal ? 'block' : 'none';
      street.required = city.required = zip.required = !isPickup && !isPersonal;
      pickupInput.required = isPickup;
    }
    form.querySelectorAll('input[name="delivery"]').forEach(function (radio) {
      radio.addEventListener('change', update);
    });
    update();
  }

  function setupBillingAddress() {
    var checkbox = document.getElementById('different-billing');
    var fields = document.getElementById('billing-fields');
    if (!checkbox || !fields) return;
    checkbox.addEventListener('change', function () {
      fields.classList.toggle('hidden-block', !checkbox.checked);
    });
  }

  function setupPacketaWidget() {
    var btn = document.getElementById('pickup-point-btn');
    var form = document.getElementById('checkout-form');
    if (!btn || !form) return;
    var display = document.getElementById('pickup_point');
    var idField = document.getElementById('pickup_point_id');

    btn.addEventListener('click', function () {
      if (typeof Packeta === 'undefined') {
        alert('Výběr pobočky se nepodařilo načíst, zkuste to prosím znovu za chvíli.');
        return;
      }
      var checked = form.querySelector('input[name="delivery"]:checked');
      var isZbox = checked && checked.value === 'zasilkovna_zbox';
      var options = {
        language: 'cs',
        vendors: isZbox ? [{ country: 'cz', group: 'zbox' }] : [{ country: 'cz' }],
      };
      Packeta.Widget.pick(PACKETA_API_KEY, function (point) {
        if (!point) return;
        var parts = [point.name, point.street, point.city].filter(Boolean);
        display.value = parts.join(', ');
        idField.value = point.id || '';
      }, options);
    });
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str == null ? '' : str;
    return div.innerHTML;
  }

  function setupWithdrawalForm() {
    var step1Form = document.getElementById('withdraw-form-step1');
    if (!step1Form) return;
    var step1 = document.getElementById('withdraw-step-1');
    var step2 = document.getElementById('withdraw-step-2');
    var step3 = document.getElementById('withdraw-step-3');
    var summaryEl = document.getElementById('withdraw-summary');
    var confirmBtn = document.getElementById('withdraw-confirm-btn');
    var backBtn = document.getElementById('withdraw-back-btn');
    var collected = null;

    step1Form.addEventListener('submit', function (e) {
      e.preventDefault();
      collected = {
        name: document.getElementById('w-name').value,
        email: document.getElementById('w-email').value,
        phone: document.getElementById('w-phone').value,
        order: document.getElementById('w-order').value,
        orderDate: document.getElementById('w-order-date').value,
        bank: document.getElementById('w-bank').value,
        address: document.getElementById('w-address').value,
        goods: document.getElementById('w-goods').value,
      };
      summaryEl.innerHTML =
        '<p><strong>Jméno:</strong> ' + escapeHtml(collected.name) + '</p>' +
        '<p><strong>E-mail:</strong> ' + escapeHtml(collected.email) + '</p>' +
        (collected.phone ? '<p><strong>Telefon:</strong> ' + escapeHtml(collected.phone) + '</p>' : '') +
        (collected.order ? '<p><strong>Číslo objednávky:</strong> ' + escapeHtml(collected.order) + '</p>' : '') +
        '<p><strong>Datum objednávky/převzetí:</strong> ' + escapeHtml(collected.orderDate) + '</p>' +
        '<p><strong>Adresa:</strong> ' + escapeHtml(collected.address) + '</p>' +
        '<p><strong>Číslo účtu pro vrácení peněz:</strong> ' + escapeHtml(collected.bank) + '</p>' +
        '<p><strong>Zboží:</strong> ' + escapeHtml(collected.goods) + '</p>';
      step1.classList.add('hidden-block');
      step2.classList.remove('hidden-block');
      step2.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    backBtn.addEventListener('click', function () {
      step2.classList.add('hidden-block');
      step1.classList.remove('hidden-block');
    });

    confirmBtn.addEventListener('click', function () {
      if (!collected) return;
      confirmBtn.disabled = true;
      backBtn.disabled = true;
      confirmBtn.textContent = 'Odesílám…';

      var now = new Date();
      var pad = function (n) { return (n < 10 ? '0' : '') + n; };
      var timestamp = pad(now.getDate()) + '.' + pad(now.getMonth() + 1) + '.' + now.getFullYear() + ' ' + pad(now.getHours()) + ':' + pad(now.getMinutes());

      var message = [
        'Odstoupení od smlouvy přijato: ' + timestamp,
        'Jméno: ' + collected.name,
        'E-mail: ' + collected.email,
        'Telefon: ' + (collected.phone || '-'),
        'Číslo objednávky: ' + (collected.order || '-'),
        'Datum objednávky/převzetí: ' + collected.orderDate,
        'Adresa: ' + collected.address,
        'Číslo účtu pro vrácení peněz: ' + collected.bank,
        'Zboží k vrácení: ' + collected.goods,
      ].join('\n');

      fetch('https://api.web3forms.com/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
          access_key: WEB3FORMS_ACCESS_KEY,
          subject: 'Odstoupení od smlouvy — ' + collected.name,
          from_name: collected.name,
          email: collected.email,
          message: message,
        }),
      })
        .then(function (res) { return res.json(); })
        .then(function (result) {
          if (!result.success) throw new Error(result.message || 'unknown error');
          step2.classList.add('hidden-block');
          step3.classList.remove('hidden-block');
          step3.innerHTML =
            '<p><strong>Vaše odstoupení od smlouvy bylo přijato dne ' + timestamp + '.</strong></p>' +
            '<p>Písemné potvrzení vám zašleme na e-mail ' + escapeHtml(collected.email) + '. Peníze vrátíme na uvedený účet nejpozději do 14 dnů od obdržení vráceného zboží.</p>';
          step3.scrollIntoView({ behavior: 'smooth', block: 'start' });
        })
        .catch(function () {
          confirmBtn.disabled = false;
          backBtn.disabled = false;
          confirmBtn.textContent = 'Potvrzuji odstoupení od smlouvy';
          alert('Odeslání se nepovedlo. Zkuste to prosím znovu, nebo nás kontaktujte přímo na flammel@flammel.cz.');
        });
    });
  }

  function renderBadge() {
    var count = cartCount(getCart());
    document.querySelectorAll('.cart-count').forEach(function (el) {
      el.textContent = count;
      el.style.display = count > 0 ? 'flex' : 'none';
    });
  }

  function renderCartPage() {
    var root = document.getElementById('cart-root');
    if (!root) return;
    var cart = getCart();
    renderFreeShippingBanner(cartTotal(cart));
    if (cart.length === 0) {
      root.innerHTML = '<div class="empty-state"><p>Váš košík je prázdný.</p><a class="btn" href="/produkty.html">Prohlédnout produkty</a></div>';
      return;
    }
    var rows = cart.map(function (item) {
      return (
        '<tr data-id="' + item.id + '">' +
        '<td><div class="cart-item-info">' +
        '<button class="remove-item" data-remove="' + item.id + '" aria-label="Odebrat">&times;</button>' +
        '<img src="' + item.image + '" alt="' + item.title + '">' +
        '<a href="' + item.url + '">' + item.title + '</a>' +
        '</div></td>' +
        '<td data-label="Cena">' + formatPrice(item.price) + '</td>' +
        '<td data-label="Množství"><div class="qty-input"><button data-dec="' + item.id + '">−</button>' +
        '<input type="text" value="' + item.qty + '" data-qty="' + item.id + '" readonly>' +
        '<button data-inc="' + item.id + '">+</button></div></td>' +
        '<td data-label="Mezisoučet">' + formatPrice(item.price * item.qty) + '</td>' +
        '</tr>'
      );
    }).join('');

    root.innerHTML =
      '<table class="cart-table"><thead><tr><th>Produkt</th><th>Cena</th><th>Množství</th><th>Mezisoučet</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table>' +
      '<div class="cart-summary"><div class="total-row"><span>Celkem</span><span>' + formatPrice(cartTotal(cart)) + '</span></div>' +
      '<a class="btn" href="/pokladna.html">Pokračovat k pokladně</a></div>';

    root.querySelectorAll('[data-inc]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var item = getCart().find(function (i) { return i.id === btn.dataset.inc; });
        updateQty(btn.dataset.inc, item.qty + 1);
        renderCartPage();
      });
    });
    root.querySelectorAll('[data-dec]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var item = getCart().find(function (i) { return i.id === btn.dataset.dec; });
        updateQty(btn.dataset.dec, item.qty - 1);
        renderCartPage();
      });
    });
    root.querySelectorAll('[data-remove]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        removeFromCart(btn.dataset.remove);
        renderCartPage();
      });
    });
  }

  function renderCheckoutSummary() {
    var root = document.getElementById('checkout-summary');
    var form = document.getElementById('checkout-form');
    if (!root) return;
    var cart = getCart();
    renderFreeShippingBanner(cartTotal(cart));
    if (cart.length === 0) {
      root.innerHTML = '<p>Váš košík je prázdný. <a href="/produkty.html">Vybrat produkty</a></p>';
      if (form) form.style.display = 'none';
      return;
    }
    var subtotal = cartTotal(cart);
    var items = cart.map(function (item) {
      return '<li><span>' + item.title + ' × ' + item.qty + '</span><span>' + formatPrice(item.price * item.qty) + '</span></li>';
    }).join('');
    root.innerHTML =
      '<ul>' + items + '</ul>' +
      '<div class="total-row total-row--sub"><span>Mezisoučet</span><span>' + formatPrice(subtotal) + '</span></div>' +
      '<div class="total-row total-row--sub" id="summary-shipping"><span>Doprava</span><span></span></div>' +
      '<div class="total-row total-row--sub" id="summary-payment"><span>Platba</span><span></span></div>' +
      '<div class="total-row total-row--grand" id="summary-grand-total"><span>Celkem</span><span></span></div>';

    function updateTotals() {
      var freeShipping = subtotal >= FREE_SHIPPING_THRESHOLD;
      var shipping = form ? shippingCostFor(selectedDelivery(form), subtotal) : 0;
      var paymentFee = form ? PAYMENT_SURCHARGE[selectedPayment(form)] || 0 : 0;
      var shippingEl = document.querySelector('#summary-shipping span:last-child');
      var paymentEl = document.querySelector('#summary-payment span:last-child');
      var grandEl = document.querySelector('#summary-grand-total span:last-child');
      if (shippingEl) shippingEl.textContent = shipping ? formatPrice(shipping) : 'Zdarma';
      if (paymentEl) paymentEl.textContent = paymentFee ? formatPrice(paymentFee) : 'Zdarma';
      if (grandEl) grandEl.textContent = formatPrice(subtotal + shipping + paymentFee);
      if (form) {
        form.querySelectorAll('.option-price[data-shipping-price]').forEach(function (el) {
          el.textContent = freeShipping ? 'Zdarma' : el.dataset.shippingPrice + ' Kč';
        });
      }
    }
    updateTotals();
    if (form) {
      form.querySelectorAll('input[name="delivery"], input[name="payment"]').forEach(function (radio) {
        radio.addEventListener('change', updateTotals);
      });
    }

    if (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var data = new FormData(form);
        var lines = cart.map(function (item) {
          return '- ' + item.title + ' x' + item.qty + ' = ' + formatPrice(item.price * item.qty);
        });
        var delivery = data.get('delivery');
        var payment = data.get('payment');
        var orderNumber = generateOrderNumber();
        var shipping = shippingCostFor(delivery, cartTotal(cart));
        var paymentFee = PAYMENT_SURCHARGE[payment] || 0;
        var deliveryDetail;
        if (delivery === 'zasilkovna_vydejni' || delivery === 'zasilkovna_zbox') {
          deliveryDetail = 'Výdejní místo: ' + (data.get('pickup_point') || '-') +
            (data.get('pickup_point_id') ? ' (ID: ' + data.get('pickup_point_id') + ')' : '');
        } else if (delivery === 'osobni') {
          deliveryDetail = 'Osobní vyzvednutí (domluvit termín)';
        } else {
          deliveryDetail = [data.get('street'), data.get('city'), data.get('zip')].filter(Boolean).join(', ');
        }
        var billingDetail = 'Stejná jako dodací';
        if (document.getElementById('different-billing').checked) {
          var billingParts = [data.get('fakt_street'), data.get('fakt_city'), data.get('fakt_zip')].filter(Boolean).join(', ');
          billingDetail = billingParts + (data.get('fakt_ico') ? ', IČO: ' + data.get('fakt_ico') : '');
        }
        var body = [
          'Číslo objednávky: ' + orderNumber,
          'Jméno: ' + data.get('name'),
          'E-mail: ' + data.get('email'),
          'Telefon: ' + data.get('phone'),
          'Doprava: ' + (DELIVERY_LABELS[delivery] || delivery) + ' (' + (shipping ? formatPrice(shipping) : 'zdarma') + ')',
          'Doručovací adresa: ' + deliveryDetail,
          'Fakturační adresa: ' + billingDetail,
          'Platba: ' + (PAYMENT_LABELS[payment] || payment) + ' (' + (paymentFee ? formatPrice(paymentFee) : 'zdarma') + ')',
          'Poznámka: ' + (data.get('note') || '-'),
          '',
          'Objednávka:',
          lines.join('\n'),
          '',
          'Mezisoučet: ' + formatPrice(cartTotal(cart)),
          'Doprava: ' + (shipping ? formatPrice(shipping) : 'Zdarma'),
          'Platba: ' + (paymentFee ? formatPrice(paymentFee) : 'Zdarma'),
          'Celkem k platbě: ' + formatPrice(cartTotal(cart) + shipping + paymentFee),
        ]
          .concat(payment === 'online' ? ['', 'Pozor: zákazník zvolil online platbu — je potřeba mu ručně poslat platební odkaz/QR platbu.'] : [])
          .join('\n');

        var submitBtn = form.querySelector('button[type="submit"]');
        var originalLabel = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Odesílám…';

        fetch('https://api.web3forms.com/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({
            access_key: WEB3FORMS_ACCESS_KEY,
            subject: 'Nová objednávka ' + orderNumber + ' z webu flammel.cz',
            from_name: data.get('name'),
            email: data.get('email'),
            message: body,
          }),
        })
          .then(function (res) { return res.json(); })
          .then(function (result) {
            if (!result.success) throw new Error(result.message || 'unknown error');
            saveCart([]);
            form.style.display = 'none';

            var confirmEl = document.createElement('div');
            confirmEl.className = 'notice-box';
            confirmEl.innerHTML =
              'Děkujeme! Objednávka <strong>č. ' + orderNumber + '</strong> byla úspěšně odeslána, brzy se vám ozveme na uvedený e-mail nebo telefon.' +
              '<br><button type="button" class="btn btn-outline" id="cancel-order-btn" style="margin-top:14px">Zrušit objednávku</button>';
            form.parentNode.insertBefore(confirmEl, form);

            document.getElementById('cancel-order-btn').addEventListener('click', function () {
              var cancelBtn = this;
              cancelBtn.disabled = true;
              cancelBtn.textContent = 'Ruším…';
              fetch('https://api.web3forms.com/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                body: JSON.stringify({
                  access_key: WEB3FORMS_ACCESS_KEY,
                  subject: 'Žádost o zrušení objednávky ' + orderNumber,
                  from_name: data.get('name'),
                  email: data.get('email'),
                  message: 'Zákazník žádá o zrušení objednávky č. ' + orderNumber + '.\nJméno: ' + data.get('name') + '\nE-mail: ' + data.get('email') + '\nTelefon: ' + data.get('phone'),
                }),
              })
                .then(function (res) { return res.json(); })
                .then(function (result) {
                  if (!result.success) throw new Error(result.message || 'unknown error');
                  cancelBtn.outerHTML = '<p style="margin-top:14px">Žádost o zrušení objednávky byla odeslána, brzy se vám ozveme.</p>';
                })
                .catch(function () {
                  cancelBtn.disabled = false;
                  cancelBtn.textContent = 'Zrušit objednávku';
                  alert('Zrušení se nepovedlo odeslat. Napište nám prosím přímo na flammel@flammel.cz.');
                });
            });
          })
          .catch(function () {
            submitBtn.disabled = false;
            submitBtn.textContent = originalLabel;
            alert('Odeslání objednávky se nepovedlo. Zkuste to prosím znovu, nebo nás rovnou kontaktujte na flammel@flammel.cz.');
          });
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    renderBadge();
    renderCartPage();
    renderCheckoutSummary();
    setupCheckoutOptions();
    setupBillingAddress();
    setupPacketaWidget();
    setupWithdrawalForm();

    document.querySelectorAll('.qty-input').forEach(function (wrap) {
      var input = wrap.querySelector('input');
      if (!input) return;
      var inc = wrap.querySelector('[data-qty-inc]');
      var dec = wrap.querySelector('[data-qty-dec]');
      if (inc) inc.addEventListener('click', function () { input.value = Math.max(1, (parseInt(input.value, 10) || 1) + 1); });
      if (dec) dec.addEventListener('click', function () { input.value = Math.max(1, (parseInt(input.value, 10) || 1) - 1); });
    });

    document.querySelectorAll('[data-add-to-cart]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var row = btn.closest('.qty-row, .quick-add');
        var qtyInput = row ? row.querySelector('.qty-input input') : null;
        var qty = qtyInput ? parseInt(qtyInput.value, 10) || 1 : 1;
        addToCart({
          id: btn.dataset.id,
          title: btn.dataset.title,
          price: parseFloat(btn.dataset.price),
          image: btn.dataset.image,
          url: btn.dataset.url,
        }, qty);
        var msg = row ? row.parentElement.querySelector('.added-msg') : document.querySelector('.added-msg');
        if (msg) {
          msg.classList.add('show');
          setTimeout(function () { msg.classList.remove('show'); }, 2500);
        } else {
          var originalText = btn.textContent;
          btn.textContent = 'Přidáno ✓';
          setTimeout(function () { btn.textContent = originalText; }, 1500);
        }
      });
    });
  });
})();
