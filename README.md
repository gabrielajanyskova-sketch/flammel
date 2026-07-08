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
data/products.csv               ceny a sklad — TOTO upravujete v Excelu (nebo se sem stáhne z Google Sheets)
data/sheet_url.txt               volitelný odkaz na Google Sheets export (viz níže)
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
- **Cena** — aktuální prodejní cena v Kč, číslo bez mezer a bez "Kč".
- **Puvodni_cena** — vyplňte jen když je produkt ve slevě: sem původní
  (přeškrtnutou) cenu, do **Cena** aktuální zlevněnou. Když produkt ve
  slevě není, nechte prázdné.
- **Skladem** — napište `Ano` nebo `Ne`.
- **Kolekce** — sem napište `Perenelle`, `Luna` nebo `Ignis`, pokud má
  produkt patřit do některé z těchto kolekcí (jinak nechte prázdné).
  Kolekce se na webu chovají jako běžné kategorie — mají vlastní kartu
  na homepage, stránku s produkty i položku v menu.

Po uložení souboru (zůstaňte u formátu CSV, Excel se může ptát, potvrďte
"Zachovat aktuální formát") spusťte:

```
python3 scripts/generate_site.py
```

Skript automaticky načte `data/products.csv` a promítne nové ceny/sklad
do všech vygenerovaných `.html` souborů. Pak stačí nahrát změněné soubory
na hosting.

## Napojení na Google Sheets (místo ručního Excelu)

Aby se ceny/sklad daly upravovat online (bez posílání souboru sem a tam) a
web si je sám natáhl přes odkaz, funguje to takto:

1. V Google Sheets vytvořte nový sešit a naimportujte do něj `data/products.csv`
   (Soubor → Import → Nahrát).
2. Klikněte na **Sdílet** → **Obecný přístup** → nastavte na *"Kdokoli s
   odkazem"* → role *Prohlížející*.
3. Zjistěte **ID sešitu** a **gid listu** z adresy v prohlížeči, adresa
   vypadá takto:
   `https://docs.google.com/spreadsheets/d/TOTO_JE_ID_SESITU/edit#gid=TOTO_JE_GID`
4. Sestavte odkaz pro export do CSV podle vzoru:
   `https://docs.google.com/spreadsheets/d/TOTO_JE_ID_SESITU/export?format=csv&gid=TOTO_JE_GID`
5. Tento odkaz vložte (samotný, na první řádek) do souboru `data/sheet_url.txt`
   místo textu, co je tam teď.

Od té chvíle si `python3 scripts/generate_site.py` sám při každém spuštění
stáhne aktuální tabulku z Google Sheets a použije ji místo lokálního
`data/products.csv` (ten se zároveň přepíše jako záložní kopie pro případ,
že by internet zrovna nešel — pak se použije ta poslední stažená).

Sloupce v tabulce zůstávají stejné jako v Excelu (ID, Nazev, Kategorie,
Cena, Puvodni_cena, Skladem) — needitujte ID.

Pozn.: Spouštění `generate_site.py` (ať už ručně, nebo naplánovaně přes
GitHub Actions/cron) je pořád potřeba, aby se stažená data promítla do
vygenerovaných `.html` souborů — tohle řešení odstraňuje jen krok
"stáhnout/nahrát CSV soubor ručně", ne krok "spustit generátor a nahrát
výsledek na hosting".

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
- **Pokladna** nekomunikuje s žádnou platební bránou — objednávka se uloží
  a e-mailem potvrdí přes backend (viz níže), ale je potřeba ji ručně
  vyřídit/poslat platební odkaz.
- **Můj účet** nemá přihlašování/registraci (žádná databáze uživatelů).

Pro plnohodnotný e-shop s platbami a účty by bylo potřeba doplnit backend —
to tento statický web úmyslně neřeší, protože WordPress export žádný takový
kód/data pro bezpečné převzetí neobsahuje (a nemělo by smysl je z Wordpressu
"opisovat", je lepší napojit standardní řešení typu platební bránu zvlášť).

## Backend (Cloudflare Worker + D1 + Resend)

Ve složce `worker/` je backend pro objednávky, nasazený na
`https://flammel-api.gabriela-janyskova.workers.dev` — pokladna
(`assets/js/cart.js`) na něj volá přímo. Odstoupení od smlouvy dál
používá Web3Forms, protože to není objednávka.

- `worker/src/index.js` — Worker s endpointy `POST /api/orders`
  (uloží objednávku do D1, pošle potvrzovací e-mail zákazníkovi a
  oznámení na `flammel@flammel.cz` přes Resend) a
  `POST /api/orders/:cislo/cancel` (zruší objednávku, pošle e-maily).
- `worker/schema.sql` — tabulky `orders` a `order_items` v D1.
- `worker/wrangler.toml` — konfigurace Workeru; sklad/ceny produktů
  dál zůstávají v Google Sheets/`products.csv`, D1 řeší jen objednávky.

Nasazení běží přes `.github/workflows/deploy-worker.yml` (spustí se
automaticky při změně `worker/**`, nebo ručně přes záložku Actions na
GitHubu). Aby workflow prošel, je potřeba v repozitáři nastavit tyto
GitHub Actions secrets (Settings → Secrets and variables → Actions):

- **CLOUDFLARE_API_TOKEN** — token s právy `Account · Workers Scripts · Edit`
  a `Account · D1 · Edit` (Cloudflare dashboard → My Profile → API Tokens →
  Create Custom Token).
- **CLOUDFLARE_ACCOUNT_ID** — najdete na Cloudflare dashboardu vpravo
  v postranním panelu (Account ID).
- **RESEND_API_KEY** — z resend.com (po ověření odesílací domény).

Workflow si D1 databázi `flammel-orders` sám vytvoří (pokud ještě
neexistuje), aplikuje schéma a nasadí Worker na `*.workers.dev`. Až
worker poprvé úspěšně naběhne, jeho URL se propíše do `cart.js` jako
další krok.
