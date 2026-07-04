#!/usr/bin/env python3
"""Generates the static flammel.cz site (plain HTML/CSS/JS) from data/content.json.

Run after scripts/extract_content.py has produced data/content.json:
    python3 scripts/generate_site.py

Price/stock come from data/products.csv (see scripts/export_products_csv.py).
If data/sheet_url.txt contains a Google Sheets CSV export link, that sheet
is downloaded and used instead (falling back to the local products.csv
copy if there's no network access) — see README.md for setup.
"""
import csv
import json
import re
import html as html_lib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / 'data' / 'content.json').read_text(encoding='utf-8'))

SITE_NAME = 'flammel'
SITE_TAGLINE = 'Ručně vyráběné přírodní dárky a dekorace s duší'
BASE_DESCRIPTION = 'Ručně vyráběné sójové svíčky, medvídci z růží, šperky a bytové dekorace. Přírodní materiály, poctivá řemeslná výroba.'


def sync_products_csv_from_sheet():
    url_path = ROOT / 'data' / 'sheet_url.txt'
    if not url_path.exists():
        return
    url = url_path.read_text(encoding='utf-8').strip()
    if not url or not url.startswith('http'):
        return
    csv_path = ROOT / 'data' / 'products.csv'
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            content = resp.read()
        csv_path.write_bytes(content)
        print('Staženo aktuální data/products.csv z Google Sheets.')
    except Exception as exc:
        print(f'Nepodařilo se stáhnout Google Sheet ({exc}), použiji poslední uložený data/products.csv.')


def apply_products_csv():
    sync_products_csv_from_sheet()
    csv_path = ROOT / 'data' / 'products.csv'
    if not csv_path.exists():
        return
    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        sample = f.read(2048)
        f.seek(0)
        delimiter = ';' if sample.count(';') >= sample.count(',') else ','
        rows = {row['ID']: row for row in csv.DictReader(f, delimiter=delimiter)}
    for p in DATA['products']:
        row = rows.get(p['id'])
        if not row:
            continue
        cena = row.get('Cena', '').strip()
        puvodni = row.get('Puvodni_cena', '').strip()
        if cena:
            if puvodni and puvodni != cena:
                p['price'] = cena
                p['sale_price'] = cena
                p['regular_price'] = puvodni
            else:
                p['price'] = cena
                p['regular_price'] = cena
                p['sale_price'] = ''
        p['stock_status'] = 'instock' if row.get('Skladem', '').strip().lower() == 'ano' else 'outofstock'


apply_products_csv()

PAGES_BY_SLUG = {p['slug']: p for p in DATA['pages']}
CAT_BY_SLUG = {c['slug']: c for c in DATA['product_cats']}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def fmt_price(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return ''
    return f"{int(round(n)):,}".replace(',', ' ') + ' Kč'


def price_block(p, tag='span'):
    price = p.get('price') or p.get('regular_price')
    regular = p.get('regular_price')
    sale = p.get('sale_price')
    if sale and regular and sale != regular:
        return (f'<{tag} class="price sale">{fmt_price(sale)}</{tag}> '
                f'<{tag} class="price-old">{fmt_price(regular)}</{tag}>')
    return f'<{tag} class="price">{fmt_price(price)}</{tag}>'


def stock_badge(p):
    if p.get('stock_status') == 'instock':
        return '<span class="stock-badge in">Skladem</span>'
    return '<span class="stock-badge out">Vyprodáno</span>'


def nav_html(active_url=''):
    items = []
    for item in DATA['nav']:
        children = item['children']
        submenu = ''
        li_class = 'nav-item'
        if children:
            submenu = '<ul class="submenu">' + ''.join(
                f'<li><a href="{c["url"]}">{c["label"]}</a></li>' for c in children
            ) + '</ul>'
        items.append(f'<li class="{li_class}"><a href="{item["url"]}">{item["label"]}</a>{submenu}</li>')
    return '<ul>' + ''.join(items) + '</ul>'


def footer_html():
    return f'''
<footer class="site-footer">
  <div class="footer-gold">
    <div class="container footer-top">
      <div class="footer-col">
        <h4>O nás</h4>
        <ul>
          <li><a href="/zakladni-informace.html">Základní informace</a></li>
          <li><a href="/reference.html">Reference</a></li>
          <li><a href="/kontakty.html">Kontakty</a></li>
        </ul>
      </div>
      <div class="footer-col">
        <h4>Produkty</h4>
        <ul>
          <li><a href="/kategorie/svicky.html">Přírodní svíčky</a></li>
          <li><a href="/kategorie/medvidci.html">Medvídci z růží</a></li>
          <li><a href="/kategorie/mineralni-kameny.html">Stylové šperky</a></li>
          <li><a href="/kategorie/makrame-dekorace.html">Trendy háčkování</a></li>
          <li><a href="/kategorie/bytove-dekorace.html">Bytové dekorace</a></li>
          <li><a href="/kategorie/akcni-nabidky.html">Vánoční dekorace</a></li>
        </ul>
      </div>
      <div class="footer-col">
        <h4>Důležité odkazy</h4>
        <ul>
          <li><a href="/moznosti-doruceni.html">Možnosti doručení</a></li>
          <li><a href="/platebni-podminky.html">Platební podmínky</a></li>
          <li><a href="/obchodni-podminky.html">Obchodní podmínky</a></li>
          <li><a href="/privacy-policy.html">Ochrana osobních údajů</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-heart">{HEART_ICON}</div>
    <div class="container footer-bottom">
      <span>NEXTER Group s.r.o. — Opletalova 1015/55, 110 00 Praha 1, IČ: 076 90 517</span>
      <span>Fio banka: 2501848682/2010 (CZK) · 2301826155/2010 (EUR)</span>
    </div>
  </div>
</footer>
'''


def base_layout(title, description, body, extra_head=''):
    full_title = f'{title} | {SITE_NAME}' if title else f'{SITE_NAME} — {SITE_TAGLINE}'
    return f'''<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{full_title}</title>
<meta name="description" content="{html_lib.escape(description or BASE_DESCRIPTION)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sen:wght@400;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/style.css">
{extra_head}
</head>
<body>
<div class="announce-bar">
  <div class="container">
    <span>Vítejte na e-shopu {SITE_NAME} &hearts;</span>
    <div class="social-row">
      <a href="http://www.facebook.com/Flammel-109217181002268" aria-label="Facebook">{FACEBOOK_ICON}</a>
      <a href="https://instagram.com/flammel.cz" aria-label="Instagram">{INSTAGRAM_ICON}</a>
      <a href="mailto:flammel@flammel.cz" aria-label="E-mail">{MAIL_ICON}</a>
    </div>
  </div>
</div>
<header class="site-header">
  <div class="container">
    <a href="/index.html" class="logo">{SITE_NAME}</a>
    <nav class="main-nav">{nav_html()}</nav>
    <div class="header-actions">
      <a href="/kosik.html" class="cart-link" aria-label="Košík">
        {CART_ICON}<span class="cart-count" style="display:none">0</span>
      </a>
      <button class="nav-toggle" aria-label="Menu" aria-expanded="false"><span class="nav-toggle-icon"></span></button>
    </div>
  </div>
</header>
<main>
{body}
</main>
{footer_html()}
<script src="/assets/js/cart.js"></script>
<script src="/assets/js/main.js"></script>
</body>
</html>
'''


def write(path, content):
    full = ROOT / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding='utf-8')


# ---------------------------------------------------------------------------
# homepage
# ---------------------------------------------------------------------------

CATEGORY_TAGLINES = {
    'svicky': ('Domácí výroba aromatických svíček', 'Pro relax'),
    'medvidci': ('Ruční dekorování z pěnových růžiček', 'Pro radost'),
    'mineralni-kameny': ('Různé typy a styly z naší dílny', 'Pro půvab'),
    'makrame-dekorace': ('Naše bavlněná produkce', 'Pro domov'),
    'bytove-dekorace': ('Vlastní originální produkty', 'Pro interiér'),
    'akcni-nabidky': ('Sezónní produkty naší značky', 'Pro Ježíška'),
}
HOME_NAV_CATS = ['svicky', 'medvidci', 'mineralni-kameny', 'makrame-dekorace', 'bytove-dekorace', 'akcni-nabidky']

def _icon(path_d):
    return f'<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{path_d}</svg>'

def _icon_fill(inner):
    return f'<svg width="34" height="34" viewBox="0 0 24 24" fill="currentColor" stroke="none">{inner}</svg>'

CAT_ICONS = {
    # Traced from the user's own reference photos of the live site.
    'svicky': _icon_fill(
        '<path d="M8.4 2.4c-1.2.6-2.1 1.5-2.1 2.4a1.9 1.9 0 0 0 3.8.5c.1-1.1-.6-2.1-1.7-2.9z"/>'
        '<rect x="6" y="8.4" width="10.4" height="9" rx="2"/>'
    ),
    'medvidci': _icon_fill(
        '<circle cx="8.2" cy="5.4" r="1.7"/><circle cx="15.8" cy="5.4" r="1.7"/>'
        '<circle cx="12" cy="8.3" r="4.1"/>'
        '<circle cx="5.7" cy="14.7" r="2.1"/><circle cx="18.3" cy="14.7" r="2.1"/>'
        '<ellipse cx="12" cy="16.2" rx="5.5" ry="5.1"/>'
        '<circle cx="8.3" cy="20.6" r="1.9"/><circle cx="15.7" cy="20.6" r="1.9"/>'
    ),
    'mineralni-kameny': _icon_fill(
        '<path d="M12 2.4 7 6.6 2.8 9.2 12 21.4l9.2-12.2L17 6.6z"/>'
        '<path d="M7 6.6h10M9.4 6.6 12 9.2M14.6 6.6 12 9.2M2.8 9.2h18.4M12 9.2 12 21.4" stroke="#cda43c" stroke-width="0.5" fill="none"/>'
    ),
    'makrame-dekorace': _icon_fill(
        '<circle cx="12" cy="7.6" r="5.2" fill="none" stroke="currentColor" stroke-width="1.4"/>'
        '<circle cx="12" cy="7.6" r="1.1"/>'
        '<path d="M12 2.4v10.4M7.2 4.4 16.8 10.8M16.8 4.4 7.2 10.8M6.8 7.6h10.4M8.3 3.7 15.7 11.5M15.7 3.7 8.3 11.5" stroke="currentColor" stroke-width="0.55" fill="none"/>'
        '<path d="M8 13v6.6M12 13.2v7.6M16 13v6.6" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" fill="none"/>'
        '<circle cx="8" cy="20" r="1"/><circle cx="12" cy="21.2" r="1"/><circle cx="16" cy="20" r="1"/>'
    ),
    'bytove-dekorace': _icon_fill(
        '<rect x="5.6" y="3.6" width="12.8" height="16.8" rx="0.8"/>'
        '<path d="M6.6 4.6 17 4.6 6.6 15z" fill="#d9b64e"/>'
    ),
    'akcni-nabidky': _icon_fill(
        '<path d="M12 1.5c.7 4 2.6 7.9 6.3 10-3.7 2.1-5.6 6-6.3 10-.7-4-2.6-7.9-6.3-10 3.7-2.1 5.6-6 6.3-10z"/>'
        '<path d="M19 2.6c.3 1.5.9 2.4 2.3 2.8-1.4.4-2 1.3-2.3 2.8-.3-1.5-.9-2.4-2.3-2.8 1.4-.4 2-1.3 2.3-2.8z"/>'
        '<path d="M4.4 14.6c.2 1 .6 1.7 1.6 2-1 .3-1.4.9-1.6 2-.2-1-.6-1.7-1.6-2 1-.3 1.4-.9 1.6-2z"/>'
    ),
}
CART_ICON = _icon('<path d="M6 8V6a6 6 0 0 1 12 0v2"/><rect x="3.5" y="8" width="17" height="13" rx="2"/>')
HEART_ICON = '<svg width="30" height="30" viewBox="0 0 24 24" fill="currentColor"><path d="M12 21s-7.5-4.6-10-9.3C.4 8.2 2 4.5 5.6 4a5 5 0 0 1 6.4 2.6A5 5 0 0 1 18.4 4c3.6.5 5.2 4.2 3.6 7.7C19.5 16.4 12 21 12 21z"/></svg>'
FACEBOOK_ICON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M13.5 21v-8h2.7l.4-3.1h-3.1V8c0-.9.3-1.5 1.6-1.5h1.7V3.7C16.5 3.6 15.5 3.5 14.3 3.5c-2.4 0-4 1.5-4 4.1v2.3H7.6v3.1h2.7v8h3.2z"/></svg>'
INSTAGRAM_ICON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3.5" y="3.5" width="17" height="17" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.2" cy="6.8" r="0.7" fill="currentColor" stroke="none"/></svg>'
MAIL_ICON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg>'


def parse_testimonials():
    content = PAGES_BY_SLUG['reference']['content']
    blocks = re.findall(r'"([^"]+)"\s*<img[^>]*alt="([^"]*)"[^>]*><cite>([^<]*)</cite>', content)
    return [{'quote': q, 'category': c} for q, _, c in blocks]


def render_home():
    cat_cards = ''.join(
        f'''<div class="cat-card-wrap">
          <a class="cat-card" href="/kategorie/{slug}.html">
            <div class="cat-icon">{CAT_ICONS.get(slug, "✦")}</div>
            <h3>{CAT_BY_SLUG[slug]['name']}</h3>
            <p>{CATEGORY_TAGLINES[slug][0]}</p>
          </a>
          <a class="cat-tag-btn" href="/kategorie/{slug}.html">{CATEGORY_TAGLINES[slug][1]}</a>
        </div>'''
        for slug in HOME_NAV_CATS
    )

    slide_images = []
    for p in DATA['products']:
        img = p['thumbnail_url'] or (p['gallery_urls'][0] if p['gallery_urls'] else '')
        if img and img not in slide_images:
            slide_images.append(img)
        if len(slide_images) >= 5:
            break
    slides = ''.join(
        f'<div class="slide{" active" if i == 0 else ""}" style="background-image:url(\'{img}\')"></div>'
        for i, img in enumerate(slide_images)
    )
    dots = ''.join(
        f'<button class="dot{" active" if i == 0 else ""}" data-slide="{i}" aria-label="Snímek {i+1}"></button>'
        for i in range(len(slide_images))
    )

    about_content = PAGES_BY_SLUG['o-nas']['content']
    figure_match = re.search(r'<figure>.*?</figure>', about_content, re.S)
    figure_html = figure_match.group(0) if figure_match else ''
    paragraphs = re.sub(r'<figure>.*?</figure>', '', about_content, flags=re.S)

    testimonials = parse_testimonials()[:6]
    testi_cards = ''.join(
        f'<div class="testi-card"><p>&ldquo;{t["quote"]}&rdquo;</p><cite>{t["category"]}</cite></div>'
        for t in testimonials
    )

    featured = [p for p in DATA['products'] if p['stock_status'] == 'instock'][:8]
    featured_cards = ''.join(product_card(p) for p in featured)

    body = f'''
<section class="hero-slider">
  <div class="slides">{slides}</div>
  <button class="slide-arrow prev" aria-label="Předchozí">&#10094;</button>
  <button class="slide-arrow next" aria-label="Další">&#10095;</button>
  <div class="slide-dots">{dots}</div>
</section>

<div class="hero-cta">
  <a class="btn" href="/produkty.html">Všechny produkty</a>
</div>

<section class="section" style="padding-top:24px">
  <div class="container">
    <div class="cat-grid home-cat-grid">{cat_cards}</div>
  </div>
</section>

<section class="section" style="background:var(--cream)">
  <div class="container">
    <div class="section-head">
      <span class="eyebrow">Oblíbené</span>
      <h2>Nejžádanější produkty</h2>
    </div>
    <div class="product-grid">{featured_cards}</div>
  </div>
</section>

<section class="section">
  <div class="container about-block">
    {figure_html}
    <div class="content">
      <span class="eyebrow">Náš příběh</span>
      <h2>O flammel</h2>
      {paragraphs}
      <a class="btn btn-outline" href="/o-nas.html">Více o nás</a>
    </div>
  </div>
</section>

<section class="section" style="background:var(--cream)">
  <div class="container">
    <div class="section-head">
      <span class="eyebrow">Reference</span>
      <h2>Co o nás říkají zákazníci</h2>
    </div>
    <div class="testi-grid">{testi_cards}</div>
  </div>
</section>
'''
    write('index.html', base_layout('', BASE_DESCRIPTION, body))


# ---------------------------------------------------------------------------
# product cards / listing
# ---------------------------------------------------------------------------

def product_card(p):
    img = p['thumbnail_url'] or (p['gallery_urls'][0] if p['gallery_urls'] else '')
    cat = p['category_names'][0] if p['category_names'] else ''
    return f'''<div class="product-card" data-cats="{','.join(p['category_slugs'])}">
      <a class="thumb" href="/produkt/{p['slug']}.html">
        <img src="{img}" alt="{html_lib.escape(p['title'])}" loading="lazy">
      </a>
      <div class="body">
        <span class="cat">{cat}</span>
        <h3><a href="/produkt/{p['slug']}.html">{p['title']}</a></h3>
        <div class="price-row">{price_block(p)}</div>
        {stock_badge(p)}
      </div>
    </div>'''


def render_product_listing(products, title, description, path, active_slug=None):
    filter_buttons = '<button class="active" data-filter="all">Vše</button>' + ''.join(
        f'<button data-filter="{slug}">{CAT_BY_SLUG[slug]["name"]}</button>' for slug in HOME_NAV_CATS
    )
    cards = ''.join(product_card(p) for p in products) if products else '<p class="empty-state">Momentálně zde nejsou žádné produkty.</p>'
    show_filter = active_slug is None
    body = f'''
<section class="page-header container">
  <span class="eyebrow">Produkty</span>
  <h1>{title}</h1>
</section>
<section class="section">
  <div class="container">
    {'<div class="filter-bar" id="cat-filter">' + filter_buttons + '</div>' if show_filter else ''}
    <div class="product-grid" id="product-grid">{cards}</div>
  </div>
</section>
'''
    extra_js = '''
<script>
document.addEventListener('DOMContentLoaded', function () {
  var bar = document.getElementById('cat-filter');
  if (!bar) return;
  var cards = document.querySelectorAll('#product-grid .product-card');
  bar.addEventListener('click', function (e) {
    var btn = e.target.closest('button');
    if (!btn) return;
    bar.querySelectorAll('button').forEach(function (b) { b.classList.remove('active'); });
    btn.classList.add('active');
    var filter = btn.dataset.filter;
    cards.forEach(function (card) {
      var cats = (card.dataset.cats || '').split(',');
      card.style.display = (filter === 'all' || cats.indexOf(filter) !== -1) ? '' : 'none';
    });
  });
});
</script>''' if show_filter else ''
    write(path, base_layout(title, description, body, extra_js))


def render_products_and_categories():
    published = DATA['products']
    render_product_listing(published, 'Produkty', 'Všechny ručně vyráběné produkty flammel.', 'produkty.html')
    used_slugs = {slug for p in published for slug in p['category_slugs']}
    for slug in used_slugs:
        cat = CAT_BY_SLUG[slug]
        subset = [p for p in published if slug in p['category_slugs']]
        render_product_listing(subset, cat['name'], f"{cat['name']} — ručně vyráběné produkty flammel.",
                                f'kategorie/{slug}.html', active_slug=slug)


def render_product_detail(p):
    images = []
    if p['thumbnail_url']:
        images.append(p['thumbnail_url'])
    images += [u for u in p['gallery_urls'] if u not in images]
    if not images:
        images = ['']
    main_img = images[0]
    thumbs = ''.join(
        f'<img src="{u}" data-full="{u}" class="{"active" if i == 0 else ""}" alt="{html_lib.escape(p["title"])} {i+1}">'
        for i, u in enumerate(images)
    ) if len(images) > 1 else ''
    cat = p['category_names'][0] if p['category_names'] else ''
    cat_slug = p['category_slugs'][0] if p['category_slugs'] else None
    breadcrumb_cat = f'<a href="/kategorie/{cat_slug}.html">{cat}</a> / ' if cat_slug else ''
    price = p.get('sale_price') or p.get('price') or p.get('regular_price')
    disabled = '' if p['stock_status'] == 'instock' else 'disabled'
    body = f'''
<section class="container" style="padding-top:32px">
  <div class="breadcrumb"><a href="/produkty.html">Produkty</a> / {breadcrumb_cat}{p['title']}</div>
  <div class="product-detail">
    <div class="gallery">
      <div class="gallery-main"><img src="{main_img}" alt="{html_lib.escape(p['title'])}"></div>
      <div class="gallery-thumbs">{thumbs}</div>
    </div>
    <div class="product-info">
      <span class="cat">{cat}</span>
      <h1>{p['title']}</h1>
      <div class="price-row">{price_block(p)} {stock_badge(p)}</div>
      <div class="qty-row">
        <div class="qty-input">
          <button type="button" data-qty-dec>−</button>
          <input type="text" id="qty" value="1">
          <button type="button" data-qty-inc>+</button>
        </div>
        <button class="btn" {disabled} data-add-to-cart
          data-id="{p['id']}" data-title="{html_lib.escape(p['title'])}"
          data-price="{price}" data-image="{main_img}" data-url="/produkt/{p['slug']}.html">
          {'Přidat do košíku' if p['stock_status'] == 'instock' else 'Vyprodáno'}
        </button>
      </div>
      <p class="added-msg">Produkt byl přidán do košíku.</p>
      <div class="product-desc">{p['description']}</div>
    </div>
  </div>
</section>
'''
    write(f'produkt/{p["slug"]}.html', base_layout(p['title'], f"{p['title']} — {cat}, flammel.cz", body))


# ---------------------------------------------------------------------------
# static content pages
# ---------------------------------------------------------------------------

def render_prose_page(slug, title, path=None):
    page = PAGES_BY_SLUG[slug]
    body = f'''
<section class="page-header container"><h1>{title}</h1></section>
<section class="section"><div class="container prose">{page['content']}</div></section>
'''
    write(path or f'{slug}.html', base_layout(title, '', body))


def render_kontakty():
    page = PAGES_BY_SLUG['kontakty']
    content = page['content']
    banking = content.split('<h2>Bankovní spojení</h2>', 1)
    banking_html = '<h2>Bankovní spojení</h2>' + banking[1] if len(banking) > 1 else ''
    body = f'''
<section class="page-header container"><h1>Kontakty</h1></section>
<section class="section">
  <div class="container">
    <div class="cat-grid">
      <div class="cat-card"><h3>E-mail</h3><p><a href="mailto:flammel@flammel.cz">flammel@flammel.cz</a></p></div>
      <div class="cat-card"><h3>Telefon</h3><p><a href="tel:+420734518868">+420 734 518 868</a></p></div>
      <div class="cat-card"><h3>Sledujte nás</h3><p>
        <a href="http://www.facebook.com/Flammel-109217181002268">Facebook</a> &middot;
        <a href="https://instagram.com/flammel.cz">Instagram</a>
      </p></div>
    </div>
    <div class="prose" style="margin-top:48px">{banking_html}</div>
  </div>
</section>
'''
    write('kontakty.html', base_layout('Kontakty', 'Kontaktní údaje a bankovní spojení flammel.cz', body))


def render_reference():
    testimonials = parse_testimonials()
    cards = ''.join(
        f'<div class="testi-card"><p>&ldquo;{t["quote"]}&rdquo;</p><cite>{t["category"]}</cite></div>'
        for t in testimonials
    )
    body = f'''
<section class="page-header container"><h1>Reference</h1><p style="color:var(--text-muted)">Co o nás říkají naši zákazníci</p></section>
<section class="section"><div class="container testi-grid">{cards}</div></section>
'''
    write('reference.html', base_layout('Reference', 'Reference a hodnocení zákazníků flammel.cz', body))


def render_produkty_redirect_page():
    pass  # produkty.html already generated by render_products_and_categories


def render_o_nas():
    page = PAGES_BY_SLUG['o-nas']
    content = page['content']
    figure_match = re.search(r'<figure>.*?</figure>', content, re.S)
    figure_html = figure_match.group(0) if figure_match else ''
    paragraphs = re.sub(r'<figure>.*?</figure>', '', content, flags=re.S)
    body = f'''
<section class="page-header container"><h1>O nás</h1></section>
<section class="section">
  <div class="container about-block">
    {figure_html}
    <div class="content">{paragraphs}</div>
  </div>
</section>
'''
    write('o-nas.html', base_layout('O nás', 'Příběh flammel — ručně vyráběné přírodní produkty s láskou.', body))


def render_informace():
    links = [
        ('Možnosti doručení', '/moznosti-doruceni.html'),
        ('Platební podmínky', '/platebni-podminky.html'),
        ('Obchodní podmínky', '/obchodni-podminky.html'),
        ('Ochrana osobních údajů', '/privacy-policy.html'),
    ]
    cards = ''.join(f'<a class="cat-card" href="{url}"><h3>{label}</h3></a>' for label, url in links)
    body = f'''
<section class="page-header container"><h1>Informace</h1></section>
<section class="section"><div class="container cat-grid">{cards}</div></section>
'''
    write('informace.html', base_layout('Informace', 'Důležité informace k nákupu na flammel.cz', body))


def render_kosik():
    body = '''
<section class="page-header container"><h1>Košík</h1></section>
<section class="section"><div class="container" id="cart-root"></div></section>
'''
    write('kosik.html', base_layout('Košík', '', body))


def render_pokladna():
    body = '''
<section class="page-header container"><h1>Pokladna</h1></section>
<section class="section">
  <div class="container checkout-grid">
    <div>
      <div class="notice-box">Tento web je statická prezentace bez napojení na platební bránu. Po odeslání formuláře se otevře e-mail s Vaší objednávkou, kterou obratem potvrdíme a domluvíme se na platbě a doručení.</div>
      <form id="checkout-form">
        <div class="form-row">
          <div class="form-group"><label for="name">Jméno a příjmení</label><input type="text" id="name" name="name" required></div>
          <div class="form-group"><label for="email">E-mail</label><input type="email" id="email" name="email" required></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label for="phone">Telefon</label><input type="tel" id="phone" name="phone" required></div>
          <div class="form-group"><label for="address">Doručovací adresa</label><input type="text" id="address" name="address" required></div>
        </div>
        <div class="form-group"><label for="note">Poznámka k objednávce</label><textarea id="note" name="note"></textarea></div>
        <button class="btn" type="submit">Odeslat objednávku e-mailem</button>
      </form>
    </div>
    <div class="order-summary" id="checkout-summary"></div>
  </div>
</section>
'''
    write('pokladna.html', base_layout('Pokladna', '', body))


def render_muj_ucet():
    body = '''
<section class="page-header container"><h1>Přihlaste se nebo se registrujte</h1></section>
<section class="section">
  <div class="container prose" style="text-align:center">
    <p>Tato statická verze webu není napojená na uživatelské účty. Pro dotaz na Vaši objednávku nebo historii nákupů nás prosím kontaktujte přímo.</p>
    <a class="btn" href="/kontakty.html">Kontaktovat nás</a>
  </div>
</section>
'''
    write('muj-ucet.html', base_layout('Můj účet', '', body))


def render_blog():
    posts = DATA['posts']
    cards = ''.join(f'''<article class="post-card">
      <h3><a href="/blog/{p['slug']}.html">{p['title']}</a></h3>
      <p class="excerpt">{re.sub('<[^<]+?>', '', p['content'])[:160]}&hellip;</p>
      <a class="readmore" href="/blog/{p['slug']}.html">Číst více →</a>
    </article>''' for p in posts)
    body = f'''
<section class="page-header container"><h1>Blog</h1></section>
<section class="section"><div class="container post-grid">{cards}</div></section>
'''
    write('blog.html', base_layout('Blog', 'Rady a tipy flammel — péče o svíčky a ruční výrobky.', body))

    for p in posts:
        pbody = f'''
<section class="page-header container"><h1>{p['title']}</h1></section>
<article class="post section"><div class="container prose">{p['content']}</div></article>
<section class="container"><a class="btn btn-outline" href="/blog.html">&larr; Zpět na blog</a></section>
'''
        write(f'blog/{p["slug"]}.html', base_layout(p['title'], '', pbody))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    render_home()
    render_products_and_categories()
    for p in DATA['products']:
        render_product_detail(p)
    render_o_nas()
    render_kontakty()
    render_reference()
    render_prose_page('zakladni-informace', 'Základní informace')
    render_prose_page('moznosti-doruceni', 'Možnosti doručení')
    render_prose_page('platebni-podminky', 'Platební podmínky')
    render_prose_page('obchodni-podminky', 'Obchodní podmínky')
    render_prose_page('privacy-policy', 'Ochrana osobních údajů')
    render_informace()
    render_kosik()
    render_pokladna()
    render_muj_ucet()
    render_blog()
    print('Site generated.')


if __name__ == '__main__':
    main()
