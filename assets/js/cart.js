// Client-side shopping cart backed by localStorage.
// There is no backend or payment gateway behind this static site, so the
// "checkout" step below composes an order e-mail instead of charging a card —
// see the notice on pokladna.html.
(function () {
  var STORAGE_KEY = 'flammel_cart';

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
    var items = cart.map(function (item) {
      return '<li><span>' + item.title + ' × ' + item.qty + '</span><span>' + formatPrice(item.price * item.qty) + '</span></li>';
    }).join('');
    root.innerHTML =
      '<ul>' + items + '</ul>' +
      '<div class="total-row"><span>Celkem</span><span>' + formatPrice(cartTotal(cart)) + '</span></div>';

    if (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var data = new FormData(form);
        var lines = cart.map(function (item) {
          return '- ' + item.title + ' x' + item.qty + ' = ' + formatPrice(item.price * item.qty);
        });
        var body = [
          'Jméno: ' + data.get('name'),
          'E-mail: ' + data.get('email'),
          'Telefon: ' + data.get('phone'),
          'Doručovací adresa: ' + data.get('address'),
          'Poznámka: ' + (data.get('note') || '-'),
          '',
          'Objednávka:',
          lines.join('\n'),
          '',
          'Celkem: ' + formatPrice(cartTotal(cart)),
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
