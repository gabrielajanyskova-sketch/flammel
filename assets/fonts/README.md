# Font Darloune

Logo a nadpisy webu (`--font-display` v `assets/css/style.css`) používají font
**Darloune** (elegantní kaligrafické písmo).

Tento font je komerční (autor WDfont) — zdarma pouze pro osobní/nekomerční
použití, pro e-shop je potřeba zakoupit komerční licenci. Proto soubor fontu
není součástí tohoto repozitáře a musíte ho sem doplnit sami (podle licence,
kterou jste zakoupili):

1. Do této složky (`assets/fonts/`) nahrajte soubory:
   - `Darloune.woff2`
   - `Darloune.woff`
   - `Darloune.otf`
2. Není nutné mít všechny tři formáty — `@font-face` v `style.css` je nastaven
   tak, aby prohlížeč použil první dostupný formát.

Dokud soubor fontu nebude doplněn, web automaticky použije náhradní
kurzívové/dekorativní písmo (fallback `cursive`), takže se nic nerozbije.
