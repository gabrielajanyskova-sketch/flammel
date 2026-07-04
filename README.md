# flammel.cz — statický web

Tento repozitář obsahuje statickou verzi e-shopu flammel.cz, převedenou
z WordPressu/WooCommerce (Elementor) do čistého HTML/CSS/JS bez závislosti
na PHP, databázi nebo WordPress pluginech.

## Struktura

```
index.html, o-nas.html, ...   generované statické stránky (kořen webu)
produkt/*.html                 detail jednotlivých produktů (121 ks)
kategorie/*.html                výpisy produktů podle kategorie
blog/*.html                     jednotlivé články
assets/css/style.css            veškeré styly
assets/js/main.js               mobilní menu, galerie produktu
assets/js/cart.js               košík (localStorage) a odeslání objednávky
assets/fonts/                   font Darloune (viz assets/fonts/README.md)
data/content.json               obsah webu (produkty, stránky, menu) — zdroj pro generátor
data/products.csv               ceny a sklad — TOTO upravujete v Excelu
scripts/extract_content.py      načte WordPress XML export a vytvoří data/content.json
scripts/export_products_csv.py  vytvoří/obnoví data/products.csv z content.json
scripts/generate_site.py        z content.json + products.csv vygeneruje všechny .html soubory
```

## Jak upravit ceny a sklad (Excel)

Otevřete `data/products.csv` v Excelu (je to tabulka oddělená středníkem,
Excel by ji měl po dvojkliku rovnou otevřít jako tabulku i s českými znaky).
Sloupce:

- **ID**, **Nazev**, **Kategorie** — jen pro orientaci, needitujte je (ID musí
  zůstat stejné, podle něj se produkt v datech dohledává).
- **Cena** — cena v Kč, číslo bez mezer a bez "Kč".
- **Skladem** — napište `Ano` nebo `Ne`.

Po uložení souboru (zůstaňte u formátu CSV, Excel se může ptát, potvrďte
"Zachovat aktuální formát") spusťte:

```
python3 scripts/generate_site.py
```

Skript automaticky načte `data/products.csv` a promítne nové ceny/sklad
do všech vygenerovaných `.html` souborů. Pak stačí nahrát změněné soubory
na hosting.

## Jak web znovu vygenerovat od nuly

Pokud budete mít úplně nový export z WordPressu (např. přidáte nové
produkty přímo tam), znovu z něj vytáhněte obsah — pozor, tím se ale
přepíše i `data/content.json`, takže `data/products.csv` je potřeba
následně obnovit příkazem níže (tím se ale ztratí ruční úpravy cen/skladu
v CSV, pokud jste je mezitím dělali — pro běžné úpravy cen/skladu stačí
rovnou upravit `data/products.csv`, viz výše, tenhle krok navíc není potřeba):

```
python3 scripts/extract_content.py cesta/k/exportu.xml
python3 scripts/export_products_csv.py   # jen pokud chcete CSV přegenerovat od nuly
python3 scripts/generate_site.py
```

## Co je potřeba doplnit před nasazením

1. **Font Darloune** — komerční licencovaný font pro logo/nadpisy, viz
   `assets/fonts/README.md`. Bez něj se použije náhradní kurzíva.
2. **Obrázky produktů** — WordPress export neobsahuje samotné soubory obrázků,
   jen jejich původní adresy na `https://www.flammel.cz/wp-content/uploads/...`.
   Vygenerované stránky proto na tyto původní adresy odkazují přímo. Pokud
   chcete mít obrázky nezávislé na starém WordPressu, stáhněte si složku
   `wp-content/uploads` z původního webu/hostingu a upravte `thumbnail_url`
   / `gallery_urls` v `data/content.json` na lokální cesty (např.
   `/assets/img/...`) před spuštěním `generate_site.py`.

## Co web (záměrně) neumí

Je to čistě statická prezentace bez backendu:

- **Košík** funguje na straně prohlížeče (`localStorage`), přežije reload,
  ale není sdílený mezi zařízeními.
- **Pokladna** nekomunikuje s žádnou platební bránou — po odeslání
  formuláře se otevře e-mail s objednávkou adresovaný na
  `flammel@flammel.cz`, který je potřeba ručně potvrdit.
- **Můj účet** nemá přihlašování/registraci (žádná databáze uživatelů).

Pro plnohodnotný e-shop s platbami a účty by bylo potřeba doplnit backend —
to tento statický web úmyslně neřeší, protože WordPress export žádný takový
kód/data pro bezpečné převzetí neobsahuje (a nemělo by smysl je z Wordpressu
"opisovat", je lepší napojit standardní řešení typu platební bránu zvlášť).
