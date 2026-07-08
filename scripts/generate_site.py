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
SITE_URL = 'https://www.flammel.cz'
SOCIAL_LINKS = [
    'http://www.facebook.com/Flammel-109217181002268',
    'https://instagram.com/flammel.cz',
]


def organization_jsonld():
    return json.dumps({
        '@context': 'https://schema.org',
        '@type': 'Organization',
        'name': SITE_NAME,
        'url': SITE_URL + '/',
        'logo': SITE_URL + '/assets/img/favicon-512.png',
        'email': 'flammel@flammel.cz',
        'telephone': '+420734518868',
        'sameAs': SOCIAL_LINKS,
    }, ensure_ascii=False)

# Display-name overrides — the client wants "Bytové dekorace" rebranded
# without touching the underlying WordPress category slug/URLs.
CATEGORY_NAME_OVERRIDES = {
    'Bytové dekorace': 'Útulný domov',
    # Not a product category, but reuses the same nav-label rename pass.
    'O NÁS': 'O FLAMMEL',
}

# New named collections (don't exist in the WordPress export — the client
# assigns products to them herself via the "Kolekce" column in
# data/products.csv, same workflow as price/stock).
NEW_COLLECTIONS = [
    {'slug': 'perenelle', 'name': 'Perenelle'},
    {'slug': 'luna', 'name': 'Luna'},
    {'slug': 'ignis', 'name': 'Ignis'},
]

# From the client's collection moodboard (Perenelle "perla v mušličce",
# Ignis "jiskra", Luna "měsíc s hvězdou").
# Exact hex codes from the client's collection moodboard.
# Whole-card gradient stops (top color, bottom tint) built from the same
# hex codes, replacing the shared gold background on collection cards.
# All the small action buttons (.cat-tag-btn / .btn) share one linen +
# gold-hover treatment, defined once in style.css.
COLLECTION_CARD_GRADIENT = {
    'perenelle': {'a': '#D8B4BC', 'b': '#f0e2e5'},
    'ignis': {'a': '#B67A3A', 'b': '#e6c9a8'},
}
# Cards themed dark to match their own artwork (Luna = night sky).
DARK_THEMED_CARDS = {'luna'}


def apply_new_collections():
    existing_slugs = {c['slug'] for c in DATA['product_cats']}
    for col in NEW_COLLECTIONS:
        if col['slug'] not in existing_slugs:
            DATA['product_cats'].append(dict(col))
    for item in DATA['nav']:
        if item['label'] == 'PRODUKTY':
            child_slugs = {c['url'] for c in item['children']}
            for col in NEW_COLLECTIONS:
                url = f"/kategorie/{col['slug']}.html"
                if url not in child_slugs:
                    item['children'].append({'label': col['name'], 'url': url})


# Categories the client didn't ask to keep — dropped entirely, including
# every product that isn't also listed under a surviving category.
REMOVED_CATEGORY_SLUGS = {'medvidci', 'makrame-dekorace', 'akcni-nabidky'}


def apply_category_removal():
    DATA['product_cats'] = [c for c in DATA['product_cats'] if c['slug'] not in REMOVED_CATEGORY_SLUGS]
    removed_product_slugs = []
    kept_products = []
    for p in DATA['products']:
        keep_names, keep_slugs = [], []
        for name, slug in zip(p['category_names'], p['category_slugs']):
            if slug not in REMOVED_CATEGORY_SLUGS:
                keep_names.append(name)
                keep_slugs.append(slug)
        if keep_slugs:
            p['category_names'], p['category_slugs'] = keep_names, keep_slugs
            kept_products.append(p)
        else:
            removed_product_slugs.append(p['slug'])
    DATA['products'] = kept_products
    for item in DATA['nav']:
        item['children'] = [c for c in item['children']
                             if c['url'] not in {f'/kategorie/{s}.html' for s in REMOVED_CATEGORY_SLUGS}]
    for slug in REMOVED_CATEGORY_SLUGS:
        (ROOT / 'kategorie' / f'{slug}.html').unlink(missing_ok=True)
    for slug in removed_product_slugs:
        (ROOT / 'produkt' / f'{slug}.html').unlink(missing_ok=True)
    print(f'Odstraněny kategorie {sorted(REMOVED_CATEGORY_SLUGS)} a {len(removed_product_slugs)} produktů.')


O_NAS_FIGURE = (
    '<figure><img src="/assets/img/o-nas-martina.jpg" title="Martina" '
    'alt="Martina" loading="lazy" /><figcaption>Vaše M ♥ flammel</figcaption></figure>'
)
O_NAS_TEXT = (
    '<p>Věřím, že ty nejkrásnější dárky nemusí být velké ani okázalé.</p>'
    '<p>Stačí drobnost, která potěší. Svíčka, kterou si zapálíte po náročném dni. '
    'Šperk, který budete nosit každý den. Nebo maličkost, která udělá radost '
    'někomu, na kom vám záleží.</p>'
    '<p>Právě z této myšlenky vznikl Flammel.</p>'
    '<p>Tvořím a vybírám produkty z kvalitních materiálů s důrazem na jednoduchost, '
    'přírodní krásu a poctivé zpracování. Každý kousek vzniká v malém množství, '
    'bez spěchu a s láskou k detailu.</p>'
    '<p>Přeji si, aby Flammel nebyl jen e-shopem, ale místem, kam se budete rádi '
    'vracet, když budete hledat dárek, který má smysl. Nebo když si budete chtít '
    'udělat radost jen tak.</p>'
    '<p>Děkuji, že jste tady.</p>'
    '<p><b>Martina ♥</b></p>'
)


def apply_category_renames():
    for c in DATA['product_cats']:
        c['name'] = CATEGORY_NAME_OVERRIDES.get(c['name'], c['name'])
    for p in DATA['products']:
        p['category_names'] = [CATEGORY_NAME_OVERRIDES.get(n, n) for n in p['category_names']]
    for item in DATA['nav']:
        item['label'] = CATEGORY_NAME_OVERRIDES.get(item['label'], item['label'])
        for child in item['children']:
            child['label'] = CATEGORY_NAME_OVERRIDES.get(child['label'], child['label'])


# Updated copy for existing WordPress products, supplied by Martina —
# content.json itself stays a straight WordPress export, so overrides
# live here instead of being hand-edited into the export.
PRODUCT_DESCRIPTION_OVERRIDES = {
    '4223': '''<p><strong>Nerezové zhášedlo na svíčky v černé barvě</strong></p>
<p>Zhášedlo na svíčky je elegantní doplněk, který ocení každý milovník svíček. Umožňuje bezpečně uhasit plamen bez zbytečného kouře a rozfouknutí horkého vosku, čímž přispívá k pohodlnější péči o svíčku i čistšímu prostředí kolem ní.</p>
<p>Díky dlouhé rukojeti se pohodlně používá také u vyšších skleněných svíček. Stačí přiložit zvonek nad plamen a během okamžiku jej bezpečně uhasit bez sfouknutí. Zhášedlo zároveň pomáhá chránit knot před zbytečným poškozením a stává se přirozenou součástí svíčkového rituálu.</p>
<p>Minimalistické provedení z nerezové oceli v matné černé barvě krásně doplní přírodní svíčky Flammel, nůžky na knot i dlouhé zápalky. Společně tvoří stylovou sadu, která potěší každého, kdo si rád vytváří útulnou atmosféru domova.</p>
<h3>Detaily produktu</h3>
<ul>
<li>materiál: nerezová ocel</li>
<li>barva: černá</li>
<li>délka: 17 cm</li>
<li>průměr zvonku: 3 cm</li>
</ul>
<h3>Péče</h3>
<p>Zhášedlo doporučujeme pravidelně otírat navlhčeným hadříkem, aby se na jeho povrchu neusazoval vosk ani saze. Díky jednoduché údržbě si zachová svůj vzhled po dlouhou dobu.</p>''',
    '5293': '''<p><strong>Nerezové zhášedlo na svíčky v barvě růžového zlata</strong></p>
<p>Zhášedlo na svíčky je elegantní doplněk, který ocení každý milovník svíček. Umožňuje bezpečně uhasit plamen bez zbytečného kouře a rozfouknutí horkého vosku, čímž přispívá k pohodlnější péči o svíčku i čistšímu prostředí kolem ní.</p>
<p>Díky dlouhé rukojeti se pohodlně používá také u vyšších skleněných svíček. Stačí přiložit zvonek nad plamen a během okamžiku jej bezpečně uhasit bez sfouknutí. Zhášedlo zároveň pomáhá chránit knot před zbytečným poškozením a stává se přirozenou součástí svíčkového rituálu.</p>
<p>Elegantní provedení z nerezové oceli v barvě růžového zlata krásně doplní přírodní svíčky Flammel, nůžky na knot i dlouhé zápalky. Společně tvoří stylovou sadu, která potěší každého, kdo si rád vytváří útulnou atmosféru domova.</p>
<h3>Detaily produktu</h3>
<ul>
<li>materiál: nerezová ocel</li>
<li>barva: růžové zlato</li>
<li>délka: 17 cm</li>
<li>průměr zvonku: 3 cm</li>
</ul>
<h3>Péče</h3>
<p>Zhášedlo doporučujeme pravidelně otírat navlhčeným hadříkem, aby se na jeho povrchu neusazoval vosk ani saze. Díky jednoduché údržbě si zachová svůj vzhled po dlouhou dobu.</p>''',
    '4225': '''<p><strong>Nerezové nůžky na knot svíčky</strong></p>
<p>Nůžky na zkracování knotu jsou nepostradatelným pomocníkem pro každého milovníka svíček. Pravidelným zastřižením knotu před zapálením podpoříte rovnoměrné hoření svíčky, omezíte kouření plamene a prodloužíte její životnost.</p>
<p>Díky dlouhým čepelím a speciálně tvarované hlavě snadno dosáhnete i ke knotu na dně vyšších skleněných svíček. Elegantní provedení z nerezové oceli z nich navíc dělá stylový doplněk, který krásně doplní vaši svíčku, zápalky i zhášedlo.</p>
<h3>Detaily produktu</h3>
<ul>
<li>kategorie: <a href="/kategorie/bytove-dekorace.html">Útulný domov</a></li>
<li>materiál: nerezová ocel</li>
<li>barva: černá</li>
<li>vhodné pro bavlněné i dřevěné knoty</li>
<li>dlouhé čepele pro pohodlné zastřižení i hluboko ve sklenici</li>
</ul>
<h3>Jak správně zkracovat knot?</h3>
<p>Před každým zapálením doporučujeme knot zkrátit na přibližně 3–5 mm. Díky tomu bude svíčka hořet klidněji, vytvoří rovnoměrné voskové jezírko a omezí se tvorba kouře i usazenin na skle.</p>
<p>Další tipy k péči o sójové svíčky najdete na <a href="/blog/pece-o-bavlneny-a-dreveny-knot.html">našem blogu</a>.</p>''',
    '5118': '''<p><strong>Nerezové nůžky na knot svíčky</strong></p>
<p>Nůžky na zkracování knotu jsou nepostradatelným pomocníkem pro každého milovníka svíček. Pravidelným zastřižením knotu před zapálením podpoříte rovnoměrné hoření svíčky, omezíte kouření plamene a prodloužíte její životnost.</p>
<p>Díky dlouhým čepelím a speciálně tvarované hlavě snadno dosáhnete i ke knotu na dně vyšších skleněných svíček. Elegantní provedení z nerezové oceli v barvě růžového zlata z nich navíc dělá stylový doplněk, který krásně doplní vaši svíčku, zápalky i zhášedlo.</p>
<h3>Detaily produktu</h3>
<ul>
<li>kategorie: <a href="/kategorie/bytove-dekorace.html">Útulný domov</a></li>
<li>materiál: nerezová ocel</li>
<li>barva: růžové zlato</li>
<li>vhodné pro bavlněné i dřevěné knoty</li>
<li>dlouhé čepele pro pohodlné zastřižení i hluboko ve sklenici</li>
</ul>
<h3>Jak správně zkracovat knot?</h3>
<p>Před každým zapálením doporučujeme knot zkrátit na přibližně 3–5 mm. Díky tomu bude svíčka hořet klidněji, vytvoří rovnoměrné voskové jezírko a omezí se tvorba kouře i usazenin na skle.</p>
<p>Další tipy k péči o sójové svíčky najdete na <a href="/blog/pece-o-bavlneny-a-dreveny-knot.html">našem blogu</a>.</p>''',
}


def apply_product_description_overrides():
    for p in DATA['products']:
        if p['id'] in PRODUCT_DESCRIPTION_OVERRIDES:
            p['description'] = PRODUCT_DESCRIPTION_OVERRIDES[p['id']]


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
    for p in DATA['products']:
        p['collection_slugs'] = []
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
        collection_names = {c['name'].lower(): c['slug'] for c in NEW_COLLECTIONS}
        raw = row.get('Kolekce', '')
        p['collection_slugs'] = [
            collection_names[part.strip().lower()]
            for part in raw.split(',')
            if part.strip().lower() in collection_names
        ]


# Clean-slate catalog per Martina's "Produkty_master" sheet — only these IDs
# (leftover WordPress products she confirmed keeping, incl. ones just needing
# Skladem flipped back to Ano) may ever appear. Everything else from the old
# WordPress export is gone for good, no matter what products.csv says.
ALLOWED_PRODUCT_IDS = {
    '4223', '4225', '5118', '5293', '5828',
}


def apply_product_allowlist():
    removed = [p for p in DATA['products'] if p['id'] not in ALLOWED_PRODUCT_IDS]
    DATA['products'] = [p for p in DATA['products'] if p['id'] in ALLOWED_PRODUCT_IDS]
    for p in removed:
        (ROOT / 'produkt' / f"{p['slug']}.html").unlink(missing_ok=True)
    # Out-of-stock items from this curated list stay visible as "Připravujeme"
    # (same treatment as the new_products.json items), not "Vyprodáno".
    for p in DATA['products']:
        if p['stock_status'] == 'outofstock':
            p['stock_status'] = 'comingsoon'
        # These are candle accessories, not candles — belong under Bytové
        # dekorace (Útulný domov); the "Hodí se k tomu" section on candle
        # pages keeps them cross-linked from Přírodní svíčky anyway.
        p['category_names'] = ['Bytové dekorace']
        p['category_slugs'] = ['bytove-dekorace']
        # Drop the hotlinked WordPress photos — new photos are coming, so
        # show the same "coming soon" placeholder as new_products.json
        # items in the meantime rather than depend on the old host.
        p['thumbnail_url'] = '/assets/img/placeholder-produkt.svg'
        p['gallery_urls'] = []
    print(f'Ponechány jen produkty z tabulky Martiny ({len(DATA["products"])}), smazáno {len(removed)} ostatních.')


def apply_new_products():
    """Add hand-authored products (no WordPress ID yet) from new_products.json —
    e.g. items Martina wants listed before their price/popis/foto are ready.
    Kept separate from content.json, which stays a straight WordPress export.
    """
    path = ROOT / 'data' / 'new_products.json'
    if not path.exists():
        return
    new_products = json.loads(path.read_text(encoding='utf-8'))
    DATA['products'].extend(new_products)
    print(f'Přidáno {len(new_products)} nových produktů (bez ceny/foto) z new_products.json.')


apply_products_csv()
apply_product_allowlist()
apply_category_renames()
apply_category_removal()
apply_new_collections()
apply_new_products()
apply_product_description_overrides()

PAGES_BY_SLUG = {p['slug']: p for p in DATA['pages']}
# The old WordPress terms linked to a downloadable .docx withdrawal form —
# replaced by the actual on-site withdrawal button/form (legally required
# "tlačítková novela" — a static download link no longer qualifies).
if 'obchodni-podminky' in PAGES_BY_SLUG:
    PAGES_BY_SLUG['obchodni-podminky']['content'] = re.sub(
        r'<a href="[^"]*Formular-odstoupeni-od-smlouvy\.docx">zde</a>',
        '<a href="/odstoupeni-od-smlouvy.html">zde</a>',
        PAGES_BY_SLUG['obchodni-podminky']['content'],
    )
CAT_BY_SLUG = {c['slug']: c for c in DATA['product_cats']}


WORKER_API_BASE = 'https://flammel-api.gabriela-janyskova.workers.dev'


def fetch_d1_products():
    """Pull price/sklad/kategorie z D1 přes Worker — postupně nahrazuje Google
    Sheets jako zdroj pravdy. Když je nedostupné (žádná síť, výpadek), tiše
    se použije to, co už je v products.csv/new_products.json — stejné
    chování jako dosavadní pád zpět při nedostupnosti Google Sheets."""
    try:
        with urllib.request.urlopen(f'{WORKER_API_BASE}/api/products', timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f'Nepodařilo se stáhnout data z Cloudflare D1 ({e}), použiji poslední uložená data.')
        return {}


def apply_d1_overrides():
    d1_products = fetch_d1_products()
    if not d1_products:
        return
    applied = 0
    for p in DATA['products']:
        row = d1_products.get(p['id'])
        if not row:
            continue
        applied += 1
        regular = row.get('regularPrice')
        sale = row.get('salePrice')
        qty = row.get('qty')
        if regular:
            if sale and sale != regular:
                p['price'] = str(sale)
                p['sale_price'] = str(sale)
                p['regular_price'] = str(regular)
            else:
                p['price'] = str(regular)
                p['regular_price'] = str(regular)
                p['sale_price'] = ''
        if qty is not None:
            if qty > 0:
                p['stock_status'] = 'instock'
            elif regular:
                p['stock_status'] = 'outofstock'
            else:
                p['stock_status'] = 'comingsoon'
        cat_slug = row.get('categorySlug')
        if cat_slug and cat_slug in CAT_BY_SLUG:
            p['category_slugs'] = [cat_slug]
            p['category_names'] = [CAT_BY_SLUG[cat_slug]['name']]
    print(f'Načteno {applied} produktů z Cloudflare D1 (cena/sklad/kategorie).')


apply_d1_overrides()


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
    if not price:
        return f'<{tag} class="price price-tbd">Cena bude brzy doplněna</{tag}>'
    if sale and regular and sale != regular:
        return (f'<{tag} class="price sale">{fmt_price(sale)}</{tag}> '
                f'<{tag} class="price-old">{fmt_price(regular)}</{tag}>')
    return f'<{tag} class="price">{fmt_price(price)}</{tag}>'


def stock_badge(p):
    status = p.get('stock_status')
    if status == 'instock':
        return '<span class="stock-badge in">Skladem</span>'
    if status == 'comingsoon':
        return '<span class="stock-badge soon">Připravujeme</span>'
    return '<span class="stock-badge out">Vyprodáno</span>'


def build_search_index():
    items = []
    for p in DATA['products']:
        img = p['thumbnail_url'] or (p['gallery_urls'][0] if p['gallery_urls'] else '')
        price = p.get('sale_price') or p.get('price') or p.get('regular_price')
        items.append({
            't': html_lib.escape(p['title']),
            'u': f"/produkt/{p['slug']}.html",
            'i': img,
            'p': fmt_price(price) if price else '',
        })
    return items


SEARCH_INDEX_JSON = json.dumps(build_search_index(), ensure_ascii=False)


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
        <h3>O mně</h3>
        <ul>
          <li><a href="/zakladni-informace.html">Základní informace</a></li>
          <li><a href="/reference.html">Reference</a></li>
          <li><a href="/kontakty.html">Kontakty</a></li>
        </ul>
      </div>
      <div class="footer-col">
        <h3>Produkty</h3>
        <ul>{''.join(f'<li><a href="/kategorie/{slug}.html">{CAT_BY_SLUG[slug]["name"]}</a></li>' for slug in HOME_NAV_CATS)}</ul>
      </div>
      <div class="footer-col">
        <h3>Důležité odkazy</h3>
        <ul>
          <li><a href="/moznosti-doruceni.html">Možnosti doručení</a></li>
          <li><a href="/platebni-podminky.html">Platební podmínky</a></li>
          <li><a href="/obchodni-podminky.html">Obchodní podmínky</a></li>
          <li><a href="/privacy-policy.html">Ochrana osobních údajů</a></li>
          <li><a href="/odstoupeni-od-smlouvy.html"><strong>Odstoupit od smlouvy</strong></a></li>
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


def base_layout(title, description, body, extra_head='', path='', noindex=False):
    full_title = f'{title} | {SITE_NAME}' if title else f'{SITE_NAME} — {SITE_TAGLINE}'
    desc = description or BASE_DESCRIPTION
    desc_attr = html_lib.escape(desc)
    title_attr = html_lib.escape(full_title)
    canonical = f'{SITE_URL}/{path}' if path else f'{SITE_URL}/'
    og_image = f'{SITE_URL}/assets/img/favicon-512.png'
    robots_tag = '<meta name="robots" content="noindex,nofollow">\n' if noindex else ''
    return f'''<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{full_title}</title>
<meta name="description" content="{desc_attr}">
{robots_tag}<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:locale" content="cs_CZ">
<meta property="og:title" content="{title_attr}">
<meta property="og:description" content="{desc_attr}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og_image}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title_attr}">
<meta name="twitter:description" content="{desc_attr}">
<meta name="twitter:image" content="{og_image}">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/img/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/assets/img/favicon-16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/assets/img/favicon-180.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Sen:wght@400;600;700;800&display=swap" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sen:wght@400;600;700;800&display=swap"></noscript>
<link rel="preload" as="font" type="font/woff2" href="/assets/fonts/Darloune.woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/style.css">
<script type="application/ld+json">{organization_jsonld()}</script>
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
      <div class="search-widget">
        <button class="search-toggle" aria-label="Hledat" aria-expanded="false">{SEARCH_ICON}</button>
        <div class="search-box">
          <input type="text" class="search-input" placeholder="Hledat produkty…" autocomplete="off">
          <div class="search-results"></div>
        </div>
      </div>
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
<script>window.SEARCH_INDEX = {SEARCH_INDEX_JSON};</script>
<script src="/assets/js/cart.js" defer></script>
<script src="/assets/js/main.js" defer></script>
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
    'svicky': ('Pro atmosféru', 'Zapálit'),
    'mineralni-kameny': ('Pro radost', 'Ozdobit se'),
    'bytove-dekorace': ('Pro pohodu', 'Zútulnit'),
    # Placeholder taglines for the new collections — easy to swap once
    # there's a final wording for each.
    'perenelle': ('Pro eleganci', 'Objevit'),
    'luna': ('Pro klid', 'Objevit'),
    'ignis': ('Pro vášeň', 'Objevit'),
}
HOME_NAV_CATS = ['svicky', 'mineralni-kameny', 'bytove-dekorace', 'perenelle', 'luna', 'ignis']

def _icon(path_d):
    return f'<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{path_d}</svg>'

# The client's own artwork, replacing the hand-drawn placeholder icons.
COLLECTION_ICON_IMAGES = {
    'perenelle': '/assets/img/icons/perenelle.png',
    'ignis': '/assets/img/icons/ignis.png',
    'luna': '/assets/img/icons/luna.png',
    'svicky': '/assets/img/icons/svicky.png',
    'bytove-dekorace': '/assets/img/icons/bytove-dekorace.png',
    'mineralni-kameny': '/assets/img/icons/mineralni-kameny.png',
}
CART_ICON = _icon('<path d="M6 9.5V7.5a6 6 0 0 1 12 0v2"/><rect x="3.5" y="9.5" width="17" height="13" rx="2"/>')
SEARCH_ICON = _icon('<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>')

def _option_icon(path_d):
    return f'<span class="option-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{path_d}</svg></span>'

# Ikony k rozlišení způsobů dopravy/platby v pokladně.
PARCEL_ICON = _option_icon('<path d="M12 3l8 4.2v9.6L12 21l-8-4.2V7.2L12 3z"/><path d="M4 7.2L12 11l8-4.2"/><path d="M12 11v10"/>')
POST_ICON = _option_icon('<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>')
STORE_ICON = _option_icon('<path d="M4 10V6a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v4"/><path d="M4 10a2.5 2.5 0 0 0 5 0 2.5 2.5 0 0 0 5 0 2.5 2.5 0 0 0 5 0"/><path d="M5 10v9h14v-9"/>')
CARD_ICON = _option_icon('<rect x="2.5" y="5.5" width="19" height="13" rx="2"/><path d="M2.5 9.5h19"/><path d="M6 14.5h4"/>')
BANK_ICON = _option_icon('<path d="M4 10l8-5 8 5"/><path d="M5 10v8M9.5 10v8M14.5 10v8M19 10v8"/><path d="M3.5 20h17"/>')
HEART_ICON = '<svg width="30" height="30" viewBox="0 0 24 24" fill="currentColor"><path d="M12 21s-7.5-4.6-10-9.3C.4 8.2 2 4.5 5.6 4a5 5 0 0 1 6.4 2.6A5 5 0 0 1 18.4 4c3.6.5 5.2 4.2 3.6 7.7C19.5 16.4 12 21 12 21z"/></svg>'
FACEBOOK_ICON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M13.5 21v-8h2.7l.4-3.1h-3.1V8c0-.9.3-1.5 1.6-1.5h1.7V3.7C16.5 3.6 15.5 3.5 14.3 3.5c-2.4 0-4 1.5-4 4.1v2.3H7.6v3.1h2.7v8h3.2z"/></svg>'
INSTAGRAM_ICON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3.5" y="3.5" width="17" height="17" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.2" cy="6.8" r="0.7" fill="currentColor" stroke="none"/></svg>'
MAIL_ICON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg>'


def parse_testimonials():
    content = PAGES_BY_SLUG['reference']['content']
    blocks = re.findall(r'"([^"]+)"\s*<img[^>]*alt="([^"]*)"[^>]*><cite>([^<]*)</cite>', content)
    return [{'quote': q, 'category': c} for q, _, c in blocks]


def render_home():
    collection_slugs = {c['slug'] for c in NEW_COLLECTIONS}

    def card_style(slug):
        g = COLLECTION_CARD_GRADIENT.get(slug)
        if not g:
            return ''
        return f' style="--card-a:{g["a"]};--card-b:{g["b"]}"'

    def icon_html(slug):
        img = COLLECTION_ICON_IMAGES.get(slug)
        return f'<img src="{img}" alt="{CAT_BY_SLUG[slug]["name"]}">' if img else '✦'

    def render_card(slug, show_badge):
        return f'''<div class="cat-card-wrap">
          <a class="cat-card{' cat-card--dark' if slug in DARK_THEMED_CARDS else ''}" href="/kategorie/{slug}.html"{card_style(slug)}>
            {'<span class="collection-badge">Kolekce</span>' if show_badge else ''}
            <div class="cat-icon">{icon_html(slug)}</div>
            <h2{' class="collection-title"' if slug in collection_slugs else ''}>{CAT_BY_SLUG[slug]['name']}</h2>
            {'' if slug in collection_slugs else f'<p>{CATEGORY_TAGLINES[slug][0]}</p>'}
          </a>
          <a class="cat-tag-btn" href="/kategorie/{slug}.html">{CATEGORY_TAGLINES[slug][1]}</a>
        </div>'''

    regular_slugs = [s for s in HOME_NAV_CATS if s not in collection_slugs]
    regular_cards = ''.join(render_card(slug, show_badge=False) for slug in regular_slugs)
    collection_cards = ''.join(render_card(slug, show_badge=False) for slug in HOME_NAV_CATS if slug in collection_slugs)

    slide_images = []
    for p in DATA['products']:
        img = p['thumbnail_url'] or (p['gallery_urls'][0] if p['gallery_urls'] else '')
        if img and img not in slide_images:
            slide_images.append(img)
        if len(slide_images) >= 5:
            break
    # While every product is still on the placeholder thumbnail (no real
    # photos yet), a full-bleed carousel of the same small icon looks
    # broken — show a plain "coming soon" hero instead of stretching it.
    no_real_photos = slide_images == ['/assets/img/placeholder-produkt.svg']
    extra_head = ''
    if no_real_photos:
        hero = '''<section class="hero-slider hero-slider--placeholder">
  <div class="hero-placeholder-content">
    <p class="hero-wordmark">flammel</p>
    <p class="hero-tagline">Nové fotky produktů už chystáme ✨</p>
  </div>
</section>'''
    else:
        slides = ''.join(
            f'<div class="slide{" active" if i == 0 else ""}" style="background-image:url(\'{img}\')"></div>'
            for i, img in enumerate(slide_images)
        )
        dots = ''.join(
            f'<button class="dot{" active" if i == 0 else ""}" data-slide="{i}" aria-label="Snímek {i+1}"></button>'
            for i in range(len(slide_images))
        )
        hero = f'''<section class="hero-slider">
  <div class="slides">{slides}</div>
  <button class="slide-arrow prev" aria-label="Předchozí">&#10094;</button>
  <button class="slide-arrow next" aria-label="Další">&#10095;</button>
  <div class="slide-dots">{dots}</div>
</section>'''
        # The hero's first slide is the LCP element — it's a CSS background-image
        # so it can't take fetchpriority itself, but preloading it gets the same effect.
        extra_head = f'<link rel="preload" as="image" fetchpriority="high" href="{slide_images[0]}">'

    testimonials = parse_testimonials()[:6]
    testi_cards = ''.join(
        f'<div class="testi-card"><p>&ldquo;{t["quote"]}&rdquo;</p><cite>{t["category"]}</cite></div>'
        for t in testimonials
    )

    featured = [p for p in DATA['products'] if p['stock_status'] == 'instock'][:8]
    featured_cards = ''.join(product_card(p) for p in featured)

    body = f'''
<h1 class="sr-only">{SITE_NAME} — {SITE_TAGLINE}</h1>
{hero}

<section class="section" style="padding-top:40px; padding-bottom:24px">
  <div class="container">
    <div class="cat-grid home-cat-grid">{regular_cards}</div>
  </div>
</section>

<section class="section" style="padding-top:24px">
  <div class="container">
    <div class="section-head">
      <h2>Kolekce našich produktů</h2>
    </div>
    <div class="cat-grid home-cat-grid">{collection_cards}</div>
    <div style="text-align:center; margin-top:44px">
      <a class="btn" href="/produkty.html">Všechny produkty</a>
    </div>
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
    {O_NAS_FIGURE}
    <div class="content">
      <span class="eyebrow">Můj příběh</span>
      <h2>O Flammel</h2>
      {O_NAS_TEXT}
      <a class="btn btn-outline" href="/o-nas.html">Více o mně</a>
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
    write('index.html', base_layout('', BASE_DESCRIPTION, body, extra_head, path=''))


# ---------------------------------------------------------------------------
# product cards / listing
# ---------------------------------------------------------------------------

def product_card(p):
    img = p['thumbnail_url'] or (p['gallery_urls'][0] if p['gallery_urls'] else '')
    cat = p['category_names'][0] if p['category_names'] else ''
    all_slugs = p['category_slugs'] + p.get('collection_slugs', [])
    price = p.get('sale_price') or p.get('price') or p.get('regular_price')
    quick_add = ''
    if p['stock_status'] != 'outofstock':
        # Rendered disabled/"Připravujeme" for comingsoon items — live-stock
        # JS re-enables it (and fills in the price) once D1 confirms both a
        # price and available quantity for this product.
        disabled = '' if p['stock_status'] == 'instock' else 'disabled'
        btn_label = 'Přidat do košíku' if p['stock_status'] == 'instock' else 'Připravujeme'
        quick_add = f'''<div class="quick-add">
          <div class="qty-input qty-input--sm">
            <button type="button" data-qty-dec aria-label="Snížit množství">−</button>
            <input type="text" value="1" readonly aria-label="Množství">
            <button type="button" data-qty-inc aria-label="Zvýšit množství">+</button>
          </div>
          <button type="button" class="btn btn-quick-add" {disabled} data-add-to-cart
            data-id="{p['id']}" data-title="{html_lib.escape(p['title'])}"
            data-price="{price}" data-image="{img}" data-url="/produkt/{p['slug']}.html">{btn_label}</button>
        </div>'''
    return f'''<div class="product-card" data-cats="{','.join(all_slugs)}">
      <a class="thumb" href="/produkt/{p['slug']}.html">
        <img src="{img}" alt="{html_lib.escape(p['title'])}" loading="lazy">
      </a>
      <div class="body">
        <span class="cat">{cat}</span>
        <h3><a href="/produkt/{p['slug']}.html">{p['title']}</a></h3>
        <div class="price-row"><span class="price-wrap" data-product-id="{p['id']}">{price_block(p)}</span></div>
        <span class="stock-badge-wrap" data-product-id="{p['id']}">{stock_badge(p)}</span> <span class="live-stock" data-product-id="{p['id']}"></span>
        {quick_add}
      </div>
    </div>'''


COLLECTION_PAGE_TEXT = {
    'perenelle': {
        'tagline': 'Jemnost, světlo a drobné radosti.',
        'body': '''<p>Perenelle je kolekce inspirovaná klidnými chvílemi, jemnými vůněmi a světlými tóny. Najdete v ní produkty, které spolu přirozeně ladí – od svíček přes šperky až po doplňky pro útulný domov.</p>
<p>Pokud hledáte dárek nebo si chcete vytvořit vlastní malý rituál, právě tady můžete snadno kombinovat jednotlivé produkty. Stejné barvy, podobná atmosféra a jeden společný pocit – lehkost, elegance a něha.</p>''',
    },
    'luna': {
        'tagline': 'Ticho, které má své kouzlo.',
        'body': '''<p>Luna patří večerům, kdy svět zpomalí a ztiší se. Beton, tmavší tóny, tlumené světlo a vůně, které připomínají klid po dlouhém dni.</p>
<p>Produkty v této kolekci byly vybrány tak, aby spolu vytvářely harmonický celek. Můžete je mezi sebou libovolně kombinovat a vytvořit si vlastní večerní kout – se svíčkou, oblíbenou knihou a drobnostmi, které promění obyčejný večer v malý rituál.</p>''',
    },
    'ignis': {
        'tagline': 'Teplo domova v každém detailu.',
        'body': '''<p>Ignis je kolekce inspirovaná hřejivou atmosférou domova. Najdete v ní vůně koření, lesa, podzimu i Vánoc, přírodní materiály a doplňky, které vybízejí ke společným chvílím.</p>
<p>Stejně jako ostatní kolekce je i Ignis sestavená tak, aby se jednotlivé produkty daly snadno kombinovat. Ať už vybíráte dárek, nebo si chcete vytvořit útulný kout jen pro sebe, vše spolu barevně i náladou přirozeně ladí.</p>''',
    },
}


def render_product_listing(products, title, description, path, active_slug=None):
    filter_buttons = '<button class="active" data-filter="all">Vše</button>' + ''.join(
        f'<button data-filter="{slug}">{CAT_BY_SLUG[slug]["name"]}</button>' for slug in HOME_NAV_CATS
    )
    cards = ''.join(product_card(p) for p in products) if products else '<p class="empty-state">Momentálně zde nejsou žádné produkty.</p>'
    show_filter = active_slug is None
    is_collection = active_slug in {c['slug'] for c in NEW_COLLECTIONS}
    eyebrow_text = 'Kolekce' if is_collection else 'Produkty'
    collection_intro = ''
    if is_collection and active_slug in COLLECTION_PAGE_TEXT:
        info = COLLECTION_PAGE_TEXT[active_slug]
        collection_intro = f'''<div class="container">
      <div class="collection-intro">
        <p class="collection-tagline">{info['tagline']}</p>
        {info['body']}
      </div>
    </div>'''
    body = f'''
<section class="page-header container">
  <span class="eyebrow">{eyebrow_text}</span>
  <h1>{title}</h1>
</section>
{collection_intro}
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
    write(path, base_layout(title, description, body, extra_js, path=path))


def render_products_and_categories():
    published = DATA['products']
    render_product_listing(published, 'Produkty', 'Všechny ručně vyráběné produkty flammel.', 'produkty.html')
    # Render every known category (not just ones with current products) so a
    # category that just lost its last product gets its page refreshed to an
    # empty state instead of leaving stale links to now-deleted products.
    collection_slugs = {c['slug'] for c in NEW_COLLECTIONS}
    for slug in CAT_BY_SLUG.keys() | collection_slugs:
        cat = CAT_BY_SLUG[slug]
        subset = [p for p in published if slug in p['category_slugs'] or slug in p.get('collection_slugs', [])]
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
    btn_label = {'instock': 'Přidat do košíku', 'comingsoon': 'Připravujeme'}.get(p['stock_status'], 'Vyprodáno')
    # Candle accessories (nůžky, zhášedlo, aromalampa) live under Útulný
    # domov, not Přírodní svíčky — cross-linking them from candle pages
    # keeps them discoverable without needing a second category assignment.
    related_section = ''
    if 'svicky' in p['category_slugs'] and p['id'] not in ALLOWED_PRODUCT_IDS:
        accessories = [q for q in DATA['products'] if q['id'] in ALLOWED_PRODUCT_IDS]
        if accessories:
            related_section = f'''
<section class="section" style="padding-top:0">
  <div class="container">
    <div class="section-head"><h2>Hodí se k tomu</h2></div>
    <div class="related-carousel">
      <button type="button" class="carousel-arrow prev" aria-label="Předchozí">&#10094;</button>
      <div class="carousel-track">{''.join(product_card(a) for a in accessories)}</div>
      <button type="button" class="carousel-arrow next" aria-label="Další">&#10095;</button>
    </div>
  </div>
</section>'''
    product_path = f'produkt/{p["slug"]}.html'
    product_url = f'{SITE_URL}/{product_path}'
    availability = {
        'instock': 'https://schema.org/InStock',
        'comingsoon': 'https://schema.org/PreOrder',
    }.get(p['stock_status'], 'https://schema.org/OutOfStock')
    plain_description = re.sub('<[^<]+?>', '', p['description']).strip()[:500]
    product_ld = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': p['title'],
        'description': plain_description,
        'sku': p['id'],
        'url': product_url,
    }
    real_images = [u for u in images if u and 'placeholder-produkt.svg' not in u]
    if real_images:
        product_ld['image'] = [u if u.startswith('http') else f'{SITE_URL}{u}' for u in real_images]
    if price:
        product_ld['offers'] = {
            '@type': 'Offer',
            'url': product_url,
            'priceCurrency': 'CZK',
            'price': str(price),
            'availability': availability,
        }
    breadcrumb_items = [{'@type': 'ListItem', 'position': 1, 'name': 'Produkty', 'item': f'{SITE_URL}/produkty.html'}]
    if cat_slug:
        breadcrumb_items.append({'@type': 'ListItem', 'position': 2, 'name': cat, 'item': f'{SITE_URL}/kategorie/{cat_slug}.html'})
    breadcrumb_items.append({'@type': 'ListItem', 'position': len(breadcrumb_items) + 1, 'name': p['title'], 'item': product_url})
    breadcrumb_ld = {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': breadcrumb_items}
    product_extra_head = (
        f'<script type="application/ld+json">{json.dumps(product_ld, ensure_ascii=False)}</script>\n'
        f'<script type="application/ld+json">{json.dumps(breadcrumb_ld, ensure_ascii=False)}</script>'
    )
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
      <div class="price-row">
        <span class="price-wrap" data-product-id="{p['id']}">{price_block(p)}</span>
      </div>
      <div class="stock-line">
        <span class="stock-badge-wrap" data-product-id="{p['id']}">{stock_badge(p)}</span>
        <span class="live-stock" data-product-id="{p['id']}"></span>
      </div>
      <div class="qty-row">
        <div class="qty-input">
          <button type="button" data-qty-dec aria-label="Snížit množství">−</button>
          <input type="text" id="qty" value="1" aria-label="Množství">
          <button type="button" data-qty-inc aria-label="Zvýšit množství">+</button>
        </div>
        <button class="btn" {disabled} data-add-to-cart
          data-id="{p['id']}" data-title="{html_lib.escape(p['title'])}"
          data-price="{price}" data-image="{main_img}" data-url="/produkt/{p['slug']}.html">
          {btn_label}
        </button>
      </div>
      <p class="added-msg">Produkt byl přidán do košíku.</p>
      <div class="product-desc">{p['description']}</div>
    </div>
  </div>
</section>
{related_section}
'''
    write(product_path, base_layout(p['title'], f"{p['title']} — {cat}, flammel.cz", body, product_extra_head, path=product_path))


# ---------------------------------------------------------------------------
# static content pages
# ---------------------------------------------------------------------------

def render_prose_page(slug, title, path=None):
    page = PAGES_BY_SLUG[slug]
    body = f'''
<section class="page-header container"><h1>{title}</h1></section>
<section class="section"><div class="container prose">{page['content']}</div></section>
'''
    page_path = path or f'{slug}.html'
    write(page_path, base_layout(title, '', body, path=page_path))


def render_odstoupeni_od_smlouvy():
    body = '''
<section class="page-header container"><h1>Odstoupení od smlouvy</h1></section>
<section class="section">
  <div class="container prose" style="max-width:760px">
    <p>Jako spotřebitel máte podle zákona právo odstoupit od smlouvy uzavřené na dálku (přes internet)
    bez udání důvodu, a to do <strong>14 dnů</strong> od převzetí zboží. Stačí vyplnit formulář níže
    a potvrdit ho — žádné psaní dopisů ani stahování formulářů není potřeba.</p>
    <p>Zboží pak zašlete do 14 dnů od odstoupení na adresu <strong>NEXTER Group s.r.o., Opletalova 1015/55,
    110 00 Praha 1</strong> (nebo ho po domluvě doručte osobně) — náklady na vrácení hradí zákazník.
    Peníze vrátíme na stejný způsob platby, jakým jste platili, nejpozději do 14 dnů od odstoupení.</p>

    <div class="notice-box" id="withdraw-step-1">
      <form id="withdraw-form-step1">
        <div class="form-row">
          <div class="form-group"><label for="w-name">Jméno a příjmení</label><input type="text" id="w-name" required></div>
          <div class="form-group"><label for="w-email">E-mail</label><input type="email" id="w-email" required></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label for="w-phone">Telefon</label><input type="tel" id="w-phone"></div>
          <div class="form-group"><label for="w-order">Číslo objednávky (pokud ho znáte)</label><input type="text" id="w-order"></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label for="w-order-date">Datum objednávky / převzetí zboží</label><input type="date" id="w-order-date" required></div>
          <div class="form-group"><label for="w-bank">Číslo účtu pro vrácení peněz</label><input type="text" id="w-bank" required></div>
        </div>
        <div class="form-group"><label for="w-address">Vaše adresa</label><input type="text" id="w-address" required></div>
        <div class="form-group"><label for="w-goods">Zboží, od jehož nákupu odstupujete</label><textarea id="w-goods" required></textarea></div>
        <button type="submit" class="btn">Pokračovat</button>
      </form>
    </div>

    <div class="notice-box hidden-block" id="withdraw-step-2">
      <p><strong>Oznamuji, že tímto odstupuji od smlouvy o nákupu níže uvedeného zboží:</strong></p>
      <div id="withdraw-summary" style="margin:14px 0"></div>
      <p>Kliknutím na tlačítko níže tuto žádost závazně odešlete flammel.cz.</p>
      <div style="display:flex; gap:12px; flex-wrap:wrap">
        <button type="button" class="btn" id="withdraw-confirm-btn">Potvrzuji odstoupení od smlouvy</button>
        <button type="button" class="btn btn-outline" id="withdraw-back-btn">Zpět upravit údaje</button>
      </div>
    </div>

    <div class="notice-box hidden-block" id="withdraw-step-3"></div>
  </div>
</section>
'''
    write('odstoupeni-od-smlouvy.html', base_layout('Odstoupení od smlouvy', 'Formulář pro odstoupení od kupní smlouvy do 14 dnů.', body, path='odstoupeni-od-smlouvy.html'))


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
    write('kontakty.html', base_layout('Kontakty', 'Kontaktní údaje a bankovní spojení flammel.cz', body, path='kontakty.html'))


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
    write('reference.html', base_layout('Reference', 'Reference a hodnocení zákazníků flammel.cz', body, path='reference.html'))


def render_o_nas():
    body = f'''
<section class="page-header container"><h1>O Flammel</h1></section>
<section class="section">
  <div class="container about-block">
    {O_NAS_FIGURE}
    <div class="content">{O_NAS_TEXT}</div>
  </div>
</section>
'''
    write('o-nas.html', base_layout('O Flammel', 'Příběh Flammel — ručně vyráběné přírodní produkty s láskou.', body, path='o-nas.html'))


def render_zakladni_informace():
    body = f'''
<section class="page-header container"><h1>Základní informace</h1></section>
<section class="section">
  <div class="container about-block">
    {O_NAS_FIGURE}
    <div class="content">{O_NAS_TEXT}</div>
  </div>
</section>
'''
    write('zakladni-informace.html', base_layout('Základní informace', 'Příběh Flammel — ručně vyráběné přírodní produkty s láskou.', body, path='zakladni-informace.html'))


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
    write('informace.html', base_layout('Informace', 'Důležité informace k nákupu na flammel.cz', body, path='informace.html'))


def render_kosik():
    body = '''
<section class="page-header container"><h1>Košík</h1></section>
<section class="section">
  <div class="container">
    <div id="free-shipping-banner"></div>
    <div id="cart-root"></div>
  </div>
</section>
'''
    write('kosik.html', base_layout('Košík', '', body, path='kosik.html', noindex=True))


def render_pokladna():
    body = '''
<section class="page-header container"><h1>Pokladna</h1></section>
<section class="section">
  <div class="container checkout-grid">
    <div>
      <div class="notice-box">Tento web je statická prezentace bez napojení na platební bránu. Po odeslání formuláře nám objednávka rovnou přijde i s vybraným způsobem dopravy a platby — obratem ji potvrdíme, u online platby zároveň pošleme platební odkaz/QR platbu.</div>
      <div id="free-shipping-banner"></div>
      <form id="checkout-form">
        <h2 class="checkout-section-title">Doprava</h2>
        <div class="option-group">
          <label class="option-item"><input type="radio" name="delivery" value="zasilkovna_adresa" checked>''' + PARCEL_ICON + '''<span>Zásilkovna – doručení na adresu</span><span class="option-price" data-shipping-price="89">89 Kč</span></label>
          <label class="option-item"><input type="radio" name="delivery" value="zasilkovna_vydejni">''' + PARCEL_ICON + '''<span>Zásilkovna – výdejní místo</span><span class="option-price" data-shipping-price="69">69 Kč</span></label>
          <label class="option-item"><input type="radio" name="delivery" value="zasilkovna_zbox">''' + PARCEL_ICON + '''<span>Zásilkovna – Z-BOX</span><span class="option-price" data-shipping-price="65">65 Kč</span></label>
          <div class="form-group" id="pickup-point-field">
            <label for="pickup_point">Vybraná pobočka / Z-BOX</label>
            <div class="pickup-picker">
              <input type="text" id="pickup_point" name="pickup_point" placeholder="Zatím nevybráno" readonly>
              <button type="button" class="btn btn-outline" id="pickup-point-btn">Vybrat na mapě</button>
            </div>
            <input type="hidden" id="pickup_point_id" name="pickup_point_id">
          </div>
          <label class="option-item"><input type="radio" name="delivery" value="ceska_posta">''' + POST_ICON + '''<span>Česká pošta</span><span class="option-price" data-shipping-price="99">99 Kč</span></label>
          <label class="option-item"><input type="radio" name="delivery" value="osobni">''' + STORE_ICON + '''<span>Osobní vyzvednutí</span><span class="option-price">Zdarma</span></label>
          <p class="option-note" id="osobni-note">Termín osobního vyzvednutí domluvíme e-mailem po odeslání objednávky.</p>
        </div>

        <h2 class="checkout-section-title">Platba</h2>
        <div class="option-group">
          <label class="option-item"><input type="radio" name="payment" value="online" checked>''' + CARD_ICON + '''<span>Online platba kartou / Google Pay</span><span class="option-price">Zdarma</span></label>
          <label class="option-item"><input type="radio" name="payment" value="prevodem">''' + BANK_ICON + '''<span>Platba předem na účet</span><span class="option-price">Zdarma</span></label>
        </div>

        <h2 class="checkout-section-title">Kontaktní a dodací údaje</h2>
        <div class="form-row">
          <div class="form-group"><label for="name">Jméno a příjmení</label><input type="text" id="name" name="name" required></div>
          <div class="form-group"><label for="email">E-mail</label><input type="email" id="email" name="email" required></div>
        </div>
        <div class="form-group"><label for="phone">Telefon</label><input type="tel" id="phone" name="phone" required></div>
        <div id="address-fields">
          <div class="form-row">
            <div class="form-group"><label for="street">Ulice a číslo popisné</label><input type="text" id="street" name="street" required></div>
            <div class="form-group"><label for="city">Město</label><input type="text" id="city" name="city" required></div>
          </div>
          <div class="form-group"><label for="zip">PSČ</label><input type="text" id="zip" name="zip" required></div>
        </div>

        <label class="option-item option-item--checkbox">
          <input type="checkbox" id="different-billing">
          <span>Chci zadat jinou fakturační adresu</span>
        </label>
        <div id="billing-fields" class="hidden-block">
          <div class="form-row">
            <div class="form-group"><label for="fakt_street">Ulice a číslo popisné</label><input type="text" id="fakt_street" name="fakt_street"></div>
            <div class="form-group"><label for="fakt_city">Město</label><input type="text" id="fakt_city" name="fakt_city"></div>
          </div>
          <div class="form-row">
            <div class="form-group"><label for="fakt_zip">PSČ</label><input type="text" id="fakt_zip" name="fakt_zip"></div>
            <div class="form-group"><label for="fakt_ico">IČO (u firem)</label><input type="text" id="fakt_ico" name="fakt_ico"></div>
          </div>
        </div>

        <div class="form-group"><label for="note">Poznámka k objednávce</label><textarea id="note" name="note"></textarea></div>
        <button class="btn" type="submit">Odeslat objednávku e-mailem</button>
      </form>
    </div>
    <div class="order-summary" id="checkout-summary"></div>
  </div>
</section>
'''
    extra_head = '<script src="https://widget.packeta.com/v6/www/js/library.js"></script>'
    write('pokladna.html', base_layout('Pokladna', '', body, extra_head, path='pokladna.html', noindex=True))


def render_404():
    body = '''
<section class="page-header container"><h1>Stránka nenalezena</h1></section>
<section class="section">
  <div class="container prose" style="text-align:center">
    <p>Omlouváme se, tuto stránku se nepodařilo najít — možná byla přesunuta nebo odkaz už neplatí.</p>
    <div style="display:flex;gap:14px;justify-content:center;flex-wrap:wrap;margin-top:8px">
      <a class="btn" href="/index.html">Zpět na hlavní stránku</a>
      <a class="btn btn-outline" href="/produkty.html">Prohlédnout produkty</a>
    </div>
  </div>
</section>
'''
    write('404.html', base_layout('Stránka nenalezena', '', body, path='404.html', noindex=True))


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
    write('muj-ucet.html', base_layout('Můj účet', '', body, path='muj-ucet.html', noindex=True))


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
    write('blog.html', base_layout('Blog', 'Rady a tipy flammel — péče o svíčky a ruční výrobky.', body, path='blog.html'))

    for p in posts:
        pbody = f'''
<section class="page-header container"><h1>{p['title']}</h1></section>
<article class="post section"><div class="container prose">{p['content']}</div></article>
<section class="container"><a class="btn btn-outline" href="/blog.html">&larr; Zpět na blog</a></section>
'''
        post_path = f'blog/{p["slug"]}.html'
        excerpt = re.sub('<[^<]+?>', '', p['content'])[:200].strip()
        article_jsonld = json.dumps({
            '@context': 'https://schema.org',
            '@type': 'BlogPosting',
            'headline': p['title'],
            'description': excerpt,
            'url': f'{SITE_URL}/{post_path}',
            'publisher': {'@type': 'Organization', 'name': SITE_NAME, 'url': SITE_URL + '/'},
        }, ensure_ascii=False)
        extra_head = f'<script type="application/ld+json">{article_jsonld}</script>'
        write(post_path, base_layout(p['title'], excerpt, pbody, extra_head, path=post_path))


# Cart/checkout/account are transactional, user-specific pages with no
# evergreen content — deliberately left out of the sitemap.
STATIC_SITEMAP_PATHS = [
    '', 'o-nas.html', 'zakladni-informace.html', 'kontakty.html', 'reference.html',
    'moznosti-doruceni.html', 'platebni-podminky.html', 'obchodni-podminky.html',
    'privacy-policy.html', 'odstoupeni-od-smlouvy.html', 'informace.html',
    'produkty.html', 'blog.html',
]


def render_sitemap_and_robots():
    paths = list(STATIC_SITEMAP_PATHS)
    paths += [f'kategorie/{c["slug"]}.html' for c in DATA['product_cats']]
    paths += [f'produkt/{p["slug"]}.html' for p in DATA['products']]
    paths += [f'blog/{p["slug"]}.html' for p in DATA['posts']]

    urls = ''.join(f'<url><loc>{SITE_URL}/{path}</loc></url>\n' for path in paths)
    sitemap = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}</urlset>
'''
    write('sitemap.xml', sitemap)

    robots = f'''User-agent: *
Allow: /

Sitemap: {SITE_URL}/sitemap.xml
'''
    write('robots.txt', robots)


def render_llms_txt():
    cat_links = '\n'.join(
        f'- [{c["name"]}]({SITE_URL}/kategorie/{c["slug"]}.html)'
        for c in DATA['product_cats']
    )
    llms = f'''# {SITE_NAME}

> {SITE_TAGLINE}. {BASE_DESCRIPTION}

## Kategorie

{cat_links}

## Další stránky

- [Všechny produkty]({SITE_URL}/produkty.html)
- [O Flammel]({SITE_URL}/o-nas.html)
- [Blog]({SITE_URL}/blog.html)
- [Kontakty]({SITE_URL}/kontakty.html)
- [Možnosti doručení]({SITE_URL}/moznosti-doruceni.html)
'''
    write('llms.txt', llms)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    render_home()
    render_products_and_categories()
    for p in DATA['products']:
        render_product_detail(p)
    render_o_nas()
    render_zakladni_informace()
    render_kontakty()
    render_reference()
    render_prose_page('moznosti-doruceni', 'Možnosti doručení')
    render_prose_page('platebni-podminky', 'Platební podmínky')
    render_prose_page('obchodni-podminky', 'Obchodní podmínky')
    render_prose_page('privacy-policy', 'Ochrana osobních údajů')
    render_odstoupeni_od_smlouvy()
    render_informace()
    render_kosik()
    render_pokladna()
    render_muj_ucet()
    render_blog()
    render_404()
    render_sitemap_and_robots()
    render_llms_txt()
    print('Site generated.')


if __name__ == '__main__':
    main()
