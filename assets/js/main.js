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

  // Clicking a nav item that has a submenu opens the list instead of
  // navigating straight to its own page — the visitor picks a specific
  // item from the dropdown rather than landing on it by accident.
  document.querySelectorAll('.nav-item').forEach(function (item) {
    var link = item.querySelector(':scope > a');
    var submenu = item.querySelector('.submenu');
    if (!submenu || !link) return;
    link.addEventListener('click', function (e) {
      e.preventDefault();
      document.querySelectorAll('.nav-item.open').forEach(function (other) {
        if (other !== item) other.classList.remove('open');
      });
      item.classList.toggle('open');
    });
  });
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.nav-item')) {
      document.querySelectorAll('.nav-item.open').forEach(function (item) { item.classList.remove('open'); });
    }
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

  // Header search — filters the embedded product index client-side,
  // since this static site has no server to query.
  var searchToggle = document.querySelector('.search-toggle');
  var searchWidget = document.querySelector('.search-widget');
  var searchInput = document.querySelector('.search-input');
  var searchResults = document.querySelector('.search-results');
  if (searchToggle && searchWidget && searchInput && searchResults) {
    searchToggle.addEventListener('click', function () {
      var isOpen = searchWidget.classList.toggle('open');
      searchToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      if (isOpen) searchInput.focus();
    });
    document.addEventListener('click', function (e) {
      if (!e.target.closest('.search-widget')) {
        searchWidget.classList.remove('open');
        searchToggle.setAttribute('aria-expanded', 'false');
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        searchWidget.classList.remove('open');
        searchToggle.setAttribute('aria-expanded', 'false');
      }
    });
    searchInput.addEventListener('input', function () {
      var index = window.SEARCH_INDEX || [];
      var q = searchInput.value.trim().toLowerCase();
      if (!q) {
        searchResults.innerHTML = '';
        searchResults.classList.remove('show');
        return;
      }
      var matches = index.filter(function (item) {
        return item.t.toLowerCase().indexOf(q) !== -1;
      }).slice(0, 8);
      searchResults.innerHTML = matches.length
        ? matches.map(function (item) {
            return '<a class="search-result" href="' + item.u + '">' +
              '<img src="' + item.i + '" alt="">' +
              '<span><span class="search-result-title">' + item.t + '</span>' +
              (item.p ? '<span class="search-result-price">' + item.p + '</span>' : '') +
              '</span></a>';
          }).join('')
        : '<p class="search-empty">Nic jsme nenašli.</p>';
      searchResults.classList.add('show');
    });
  }
});
