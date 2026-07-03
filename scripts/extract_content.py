#!/usr/bin/env python3
"""Extracts public site content (pages, products, blog posts, menu, categories)
from a WordPress/WooCommerce eXtended RSS (WXR) export into data/content.json.

Only publicly published content is extracted. Orders, coupons, customer data
and draft products are intentionally left out.

Usage:
    python3 scripts/extract_content.py /path/to/export.WordPress.xml
"""
import sys
import re
import json
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {
    'wp': 'http://wordpress.org/export/1.2/',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'excerpt': 'http://wordpress.org/export/1.2/excerpt/',
}

ROOT = Path(__file__).resolve().parent.parent

FOOTER_MARKERS = ['<h3>O NÁS</h3>', '<h3 >O NÁS</h3>']


def text(el, tag):
    e = el.find(tag, NS)
    return e.text if e is not None and e.text else ''


def strip_style_attrs(html):
    html = re.sub(r'\s+style="[^"]*"', '', html)
    return re.sub(r"\s+style='[^']*'", '', html)


def remove_svg(html):
    return re.sub(r'<svg[\s\S]*?</svg>', '', html)


def remove_empty_anchors(html):
    for _ in range(3):
        html = re.sub(r'<a\b[^>]*>\s*</a>', '', html)
    return html


def remove_wp_comments_shortcodes(html):
    html = re.sub(r'<!--\s*/?wp:[^>]*-->', '', html)
    return re.sub(r'\[/?woocommerce_[a-z_]*\]', '', html)


def strip_target_rel(html):
    html = re.sub(r'\s+target="_blank"', '', html)
    return re.sub(r'\s+rel="noopener"', '', html)


def collapse_whitespace(html):
    html = re.sub(r'[ \t]+', ' ', html)
    html = re.sub(r'\n\s*\n+', '\n', html)
    html = re.sub(r'>\s+<', '><', html)
    return html.strip()


def strip_shared_footer(html):
    for marker in FOOTER_MARKERS:
        idx = html.find(marker)
        if idx != -1:
            return html[:idx].strip()
    return html


def strip_leading_stat_counters(html):
    # Elementor counter widgets render as bare uppercase-label/digit/plus
    # text with no markup in the RSS fallback content (the real numbers only
    # exist as client-side JS state), so we drop this decorative junk.
    return re.sub(r'^[\s0-9+A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]+(?=<)', '', html).strip()


def clean_content(html, is_page=False):
    if not html:
        return ''
    html = remove_wp_comments_shortcodes(html)
    html = remove_svg(html)
    html = strip_style_attrs(html)
    html = strip_target_rel(html)
    html = remove_empty_anchors(html)
    html = collapse_whitespace(html)
    if is_page:
        html = strip_shared_footer(html)
        html = strip_leading_stat_counters(html)
    return html.strip()


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    src = Path(sys.argv[1])
    tree = ET.parse(src)
    channel = tree.getroot().find('channel')

    attachments = {}
    products = []
    pages = []
    posts = []
    menu_items = []
    product_cats = {}

    for it in channel.findall('item'):
        ptype = text(it, 'wp:post_type')
        post_id = text(it, 'wp:post_id')
        title = text(it, 'title')
        status = text(it, 'wp:status')
        name = text(it, 'wp:post_name')
        content_el = it.find('content:encoded', NS)
        content_val = content_el.text if content_el is not None and content_el.text else ''
        postmeta = {}
        for pm in it.findall('wp:postmeta', NS):
            postmeta[text(pm, 'wp:meta_key')] = text(pm, 'wp:meta_value')
        cats = [c.text for c in it.findall('category') if c.get('domain') == 'product_cat']

        if ptype == 'attachment':
            guid_el = it.find('guid')
            attachments[post_id] = guid_el.text if guid_el is not None else ''
        elif ptype == 'product' and status == 'publish':
            products.append({
                'id': post_id, 'title': title, 'slug': name,
                'description': clean_content(content_val),
                'categories': cats,
                'price': postmeta.get('_price', ''),
                'regular_price': postmeta.get('_regular_price', ''),
                'sale_price': postmeta.get('_sale_price', ''),
                'sku': postmeta.get('_sku', ''),
                'stock_status': postmeta.get('_stock_status', 'instock'),
                'thumbnail_id': postmeta.get('_thumbnail_id', ''),
                'gallery_ids': [g for g in postmeta.get('_product_image_gallery', '').split(',') if g],
            })
        elif ptype == 'page' and status == 'publish':
            pages.append({
                'id': post_id, 'title': title, 'slug': name,
                'content': clean_content(content_val, is_page=True),
            })
        elif ptype == 'post' and status == 'publish':
            posts.append({
                'id': post_id, 'title': title, 'slug': name,
                'content': clean_content(content_val),
            })
        elif ptype == 'nav_menu_item':
            menu_items.append({
                'id': post_id,
                'object_type': postmeta.get('_menu_item_object'),
                'object_id': postmeta.get('_menu_item_object_id'),
                'parent': postmeta.get('_menu_item_menu_item_parent', '0'),
                'order': int(text(it, 'wp:menu_order') or 0),
            })

    for term in channel.findall('wp:term', NS):
        if text(term, 'wp:term_taxonomy') == 'product_cat':
            product_cats[text(term, 'wp:term_id')] = {
                'slug': text(term, 'wp:term_slug'),
                'name': text(term, 'wp:term_name'),
            }

    pages_by_id = {p['id']: p for p in pages}

    def resolve_menu_label(mi):
        if mi['object_type'] == 'page':
            p = pages_by_id.get(mi['object_id'])
            return p['title'] if p else ''
        if mi['object_type'] == 'product_cat':
            c = product_cats.get(mi['object_id'])
            return c['name'] if c else ''
        return ''

    def resolve_menu_url(mi):
        if mi['object_type'] == 'page':
            p = pages_by_id.get(mi['object_id'])
            return f"/{p['slug']}.html" if p and p['slug'] else '/'
        if mi['object_type'] == 'product_cat':
            c = product_cats.get(mi['object_id'])
            return f"/kategorie/{c['slug']}.html" if c else '#'
        return '#'

    nav = []
    top = sorted([m for m in menu_items if m['parent'] == '0'], key=lambda m: m['order'])
    for t in top:
        children = sorted([m for m in menu_items if m['parent'] == t['id']], key=lambda m: m['order'])
        nav.append({
            'label': resolve_menu_label(t),
            'url': resolve_menu_url(t),
            'children': [{'label': resolve_menu_label(c), 'url': resolve_menu_url(c)} for c in children],
        })

    cat_name_to_slug = {v['name']: v['slug'] for v in product_cats.values()}
    for p in products:
        p['category_names'] = p['categories']
        p['category_slugs'] = [cat_name_to_slug[c] for c in p['categories'] if c in cat_name_to_slug]

    def attachment_url(aid):
        return attachments.get(aid, '')

    for p in products:
        p['thumbnail_url'] = attachment_url(p['thumbnail_id'])
        p['gallery_urls'] = [attachment_url(g) for g in p['gallery_ids'] if attachment_url(g)]

    out = {
        'nav': nav,
        'pages': pages,
        'posts': posts,
        'products': products,
        'product_cats': list(product_cats.values()),
    }
    out_path = ROOT / 'data' / 'content.json'
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'Wrote {out_path} — {len(pages)} pages, {len(posts)} posts, {len(products)} products')


if __name__ == '__main__':
    main()
