# River Azoth player guide (static site)

Plain HTML, CSS and JS; no build step. Served by GitHub Pages from `.github/workflows/guide-pages.yml`.

- Prose pages (`index`, `start`, `walkthrough`, `river`) are hand-written HTML.
- Reference pages (`pokedex`, `moves`, `items`, `locations`, `trainers`) are shells; `guide.js` renders them from `data/*.json`.
- `data/` is generated from the built ROM. Do not edit it by hand. After any change to the patch, rebuild and regenerate:

```
RHT_EDITION=river python3 scripts/insert.py
python3 scripts/hackdb.py build --rom build/Mercury_EN.gba     # only needed for trainer locations
python3 scripts/guide_data.py                                   # writes docs/guide/data/*.json
```

- Preview locally (fetching JSON needs a web server, not file://): `cd docs && python3 -m http.server`, then open `/guide/`.
- Battle teams inside prose pages use `<div class="bw" data-t="66,72"></div>` (trainer ids from the ROM); Frontier Brains use `<div class="fr" data-brain="Lance">`.
- The `data/` JSON holds game tables (stats, moves, items, trainer teams, wild tables) and the Frontier's own sets. It contains no ROM bytes.
