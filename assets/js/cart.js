// Client-side shopping cart backed by localStorage.
// There is no backend or payment gateway behind this static site, so the
// "checkout" step below composes an order e-mail instead of charging a card —
// see the notice on pokladna.html.
(function () {
  var STORAGE_KEY = 'flammel_cart';
  var PACKETA_API_KEY = 'b8b56c3f9361b7175d2bd60f70b40c7a';

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
      var shipping = form ? SHIPPING_PRICES[selectedDelivery(form)] || 0 : 0;
      var paymentFee = form ? PAYMENT_SURCHARGE[selectedPayment(form)] || 0 : 0;
      var shippingEl = document.querySelector('#summary-shipping span:last-child');
      var paymentEl = document.querySelector('#summary-payment span:last-child');
      var grandEl = document.querySelector('#summary-grand-total span:last-child');
      if (shippingEl) shippingEl.textContent = shipping ? formatPrice(shipping) : 'Zdarma';
      if (paymentEl) paymentEl.textContent = paymentFee ? formatPrice(paymentFee) : 'Zdarma';
      if (grandEl) grandEl.textContent = formatPrice(subtotal + shipping + paymentFee);
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
        var shipping = SHIPPING_PRICES[delivery] || 0;
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
        ].join('\n');
        var mailto = 'mailto:flammel@flammel.cz?subject=' + encodeURIComponent('Nová objednávka z webu flammel.cz') +
          '&body=' + encodeURIComponent(body);
        window.location.href = mailto;
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

    document.querySelectorAll('[data-add-to-cart]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var qtyInput = document.getElementById('qty');
        var qty = qtyInput ? parseInt(qtyInput.value, 10) || 1 : 1;
        addToCart({
          id: btn.dataset.id,
          title: btn.dataset.title,
          price: parseFloat(btn.dataset.price),
          image: btn.dataset.image,
          url: btn.dataset.url,
        }, qty);
        var msg = document.querySelector('.added-msg');
        if (msg) {
          msg.classList.add('show');
          setTimeout(function () { msg.classList.remove('show'); }, 2500);
        }
      });
    });

    var qtyInput = document.getElementById('qty');
    if (qtyInput) {
      document.querySelectorAll('[data-qty-inc]').forEach(function (b) {
        b.addEventListener('click', function () { qtyInput.value = Math.max(1, (parseInt(qtyInput.value, 10) || 1) + 1); });
      });
      document.querySelectorAll('[data-qty-dec]').forEach(function (b) {
        b.addEventListener('click', function () { qtyInput.value = Math.max(1, (parseInt(qtyInput.value, 10) || 1) - 1); });
      });
    }
  });
})();
