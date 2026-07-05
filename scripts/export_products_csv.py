#!/usr/bin/env python3
"""Exports data/content.json products into data/products.csv for editing in Excel.

Run once to (re)create the starting CSV from the current product data:
    python3 scripts/export_products_csv.py

After that, edit data/products.csv directly (price/stock) — you normally
don't need to run this script again. generate_site.py reads products.csv
on every run and applies it on top of data/content.json.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / 'data' / 'content.json').read_text(encoding='utf-8'))

out_path = ROOT / 'data' / 'products.csv'
with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f, delimiter=';')
    writer.writerow(['ID', 'Nazev', 'Kategorie', 'Cena', 'Puvodni_cena', 'Skladem', 'Kolekce'])
    for p in DATA['products']:
        regular = p.get('regular_price') or ''
        sale = p.get('sale_price') or ''
        on_sale = sale and regular and sale != regular
        writer.writerow([
            p['id'],
            p['title'],
            ', '.join(p['category_names']),
            sale if on_sale else (regular or p.get('price') or ''),
            regular if on_sale else '',
            'Ano' if p.get('stock_status') == 'instock' else 'Ne',
            '',
        ])

print(f'Wrote {out_path} — {len(DATA["products"])} produktů')
