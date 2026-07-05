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

  // Highlight the nav link matching the current page (and its parent
  // dropdown) in gold, like the original site's active-category style.
  var currentPath = window.location.pathname;
  document.querySelectorAll('.main-nav a').forEach(function (link) {
    var linkPath = new URL(link.href).pathname;
    if (linkPath === currentPath) {
      link.classList.add('nav-active');
      var parentItem = link.closest('.nav-item');
      if (parentItem) {
        var topLink = parentItem.querySelector(':scope > a');
        if (topLink && topLink !== link) topLink.classList.add('nav-active');
      }
    }
  });

  // Homepage hero image slider
  var slider = document.querySelector('.hero-slider');
  if (slider) {
    var slides = slider.querySelectorAll('.slide');
    var dots = slider.querySelectorAll('.dot');
    var current = 0;
    var timer;

    function goTo(index) {
      current = (index + slides.length) % slides.length;
      slides.forEach(function (s, i) { s.classList.toggle('active', i === current); });
      dots.forEach(function (d, i) { d.classList.toggle('active', i === current); });
    }
    function restartAutoplay() {
      clearInterval(timer);
      timer = setInterval(function () { goTo(current + 1); }, 5000);
    }
    slider.querySelector('.slide-arrow.prev').addEventListener('click', function () { goTo(current - 1); restartAutoplay(); });
    slider.querySelector('.slide-arrow.next').addEventListener('click', function () { goTo(current + 1); restartAutoplay(); });
    dots.forEach(function (dot, i) {
      dot.addEventListener('click', function () { goTo(i); restartAutoplay(); });
    });
    if (slides.length > 1) restartAutoplay();
  }

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
