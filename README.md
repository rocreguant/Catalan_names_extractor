# Catalan names extractor

Downloads the full Idescat **"Noms de la població"** ranking
(`https://www.idescat.cat/noms/?var=1&ord=0&posicio=N`) by walking every
`posicio` page, and saves it into one CSV file.

## Output columns

| column | source |
|---|---|
| `posicio` | Pos. |
| `sexe` | Sexe (H = home, D = dona) |
| `nom` | Nom |
| `frequencia` | Rànquing freqüència |
| `per_mil` | ‰ |
| `edat_mitjana` | Edat mitjana |
| `compost` | `True` if the name has two or more words (split on spaces or hyphens), e.g. `ANA ROSA` |
| `num_lletres` | number of letters in the name; spaces, hyphens, apostrophes and `·` are not counted |
| `a_viccionari` | `True` if the name is in the Catalan Wiktionary [Llista de noms propis en català](https://ca.wiktionary.org/wiki/Viccionari:Llista_de_noms_propis_en_català) |

### How the Wiktionary match works

The list is downloaded once per run through the Wiktionary API. Both sides are
compared ignoring case and accents (`MARTÍ`, `Martí` and `MARTI` all match),
with hyphens treated as spaces and `l·l` treated as `ll`. A composed name
counts only if every one of its words is on the list (or the full name is):
`ANA ROSA` needs both `Ana` and `Rosa`, one word alone is not enough.
Use `--wiktionary-file list.txt` to read a saved copy of the page's wikitext,
or `--skip-wiktionary` to leave the column out.

## Usage

```bash
pip install -r requirements.txt
python scrape_names.py                         # writes noms_idescat.csv
python scrape_names.py --max-pages 2           # quick check on the first 2 pages
python scrape_names.py -o noms.csv --delay 2   # custom output and politer pacing
```

The script starts at `posicio=0` (the first name), advances by the number of
rows each page shows, and skips duplicates. It stops after 2 pages in a row
whose names table is empty (change with `--empty-pages-to-stop`). It waits
`--delay` seconds between requests (default 1 s).

Everything is logged to `scrape_names.log` (change with `--log-file`):
progress per page, plus warnings and errors for pages that failed to
download (retried 4 times, then skipped), empty pages, duplicate names,
malformed rows and problems loading the Wiktionary list.

The CSV is written as UTF-8 with BOM so Excel shows accents correctly.

## Tests

```bash
pip install pytest
pytest tests
```
