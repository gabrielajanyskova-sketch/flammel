# Font Darloune

Logo a nadpisy webu (`--font-display` v `assets/css/style.css`) používají font
**Darloune** (elegantní kaligrafické písmo).

Soubory `Darloune.otf`, `Darloune.woff` a `Darloune.woff2` jsou součástí
repozitáře (woff/woff2 vygenerované z dodaného `.otf`). Tento font je
komerční (autor WDfont) — ověřte si prosím, že máte pro použití na e-shopu
platnou komerční licenci (ne jen osobní/nekomerční).

Pokud by soubory někdy chyběly nebo je bude potřeba nahradit novou verzí,
`@font-face` v `style.css` je nastaven tak, aby prohlížeč použil první
dostupný formát, a v mezidobí bez souboru automaticky naskočí náhradní
kurzívové písmo (fallback `cursive`), takže se nic nerozbije.
