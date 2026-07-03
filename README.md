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
scripts/extract_content.py      načte WordPress XML export a vytvoří data/content.json
scripts/generate_site.py        z data/content.json vygeneruje všechny .html soubory
```

## Jak web znovu vygenerovat

Pokud upravíte obsah v exportu z WordPressu nebo přímo v `data/content.json`,
znovu vygenerujte stránky:

```
python3 scripts/extract_content.py cesta/k/exportu.xml   # jen pokud máte nový XML export
python3 scripts/generate_site.py
```

Skript `generate_site.py` přepíše všechny `.html` soubory podle šablon
v sobě a dat v `data/content.json`.

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
