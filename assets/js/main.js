// Mobile navigation + product gallery interactions
document.addEventListener('DOMContentLoaded', function () {
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.querySelector('.main-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', nav.classList.contains('open'));
    });
  }

  // On touch/mobile, tapping a nav item with a submenu opens it instead of navigating away.
  document.querySelectorAll('.nav-item').forEach(function (item) {
    var link = item.querySelector(':scope > a');
    var submenu = item.querySelector('.submenu');
    if (!submenu || !link) return;
    link.addEventListener('click', function (e) {
      if (window.innerWidth <= 720) {
        e.preventDefault();
        item.classList.toggle('open');
      }
    });
  });

  // Product gallery thumbnail swap
  var mainImg = document.querySelector('.gallery-main img');
  var thumbs = document.querySelectorAll('.gallery-thumbs img');
  thumbs.forEach(function (thumb) {
    thumb.addEventListener('click', function () {
      if (!mainImg) return;
      mainImg.src = thumb.dataset.full || thumb.src;
      thumbs.forEach(function (t) { t.classList.remove('active'); });
      thumb.classList.add('active');
    });
  });
});
