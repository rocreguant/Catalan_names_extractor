#!/usr/bin/env python3
"""Scrape the Idescat "Noms de la població" table into a single CSV file.

Source pages look like:
    https://www.idescat.cat/noms/?var=1&ord=0&posicio=N

Each page shows a slice of the ranking table with the columns
Pos., Sexe, Nom, Rànquing freqüència, ‰ and Edat mitjana.
This script walks every ``posicio`` page, collects all rows, and writes them
to one CSV with two extra columns:

    compost      -> True if the name has two or more words (e.g. "ANA ROSA")
    num_lletres  -> number of letters in the name (spaces, hyphens and
                    other punctuation are not counted)

Usage:
    pip install -r requirements.txt
    python scrape_names.py                      # writes noms_idescat.csv
    python scrape_names.py -o noms.csv --delay 1.5
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
import unicodedata

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.idescat.cat/noms/"
DEFAULT_PARAMS = {"var": "1", "ord": "0"}
USER_AGENT = "Mozilla/5.0 (compatible; catalan-names-extractor/1.0)"

# Output column names, in order.
COLUMNS = [
    "posicio",
    "sexe",
    "nom",
    "frequencia",
    "per_mil",
    "edat_mitjana",
    "compost",
    "num_lletres",
]

# Map from (normalized) header text on the page to our column name.
HEADER_MAP = {
    "pos": "posicio",
    "sexe": "sexe",
    "nom": "nom",
    "ranquing frequencia": "frequencia",
    "frequencia": "frequencia",
    "‰": "per_mil",
    "edat mitjana": "edat_mitjana",
}


def _norm(text: str) -> str:
    """Lowercase, strip accents, sort arrows and punctuation from header text."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("‰", " ‰ ")
    text = re.sub(r"[^\w‰ ]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def parse_number(text: str) -> float | int | None:
    """Parse Catalan-formatted numbers: '1.234' -> 1234, '44,6' -> 44.6."""
    text = text.strip().replace("\xa0", "").replace(" ", "")
    if not text or text in {"-", "..", "—"}:
        return None
    text = text.replace(".", "").replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        return None
    return int(value) if value.is_integer() and "." not in text else value


def is_composed(name: str) -> bool:
    """True if the name has two or more words, e.g. 'ANA ROSA' or 'JOAN-MARC'."""
    return len([w for w in re.split(r"[\s\-]+", name.strip()) if w]) >= 2


def count_letters(name: str) -> int:
    """Number of letters in the name, ignoring spaces, hyphens, apostrophes, '·'."""
    return sum(1 for c in name if c.isalpha())


def find_names_table(soup: BeautifulSoup):
    """Return (table, column_index_map) for the table whose headers include Nom and Sexe."""
    for table in soup.find_all("table"):
        header_cells = None
        thead = table.find("thead")
        rows = thead.find_all("tr") if thead else table.find_all("tr")
        # Use the header row that contains the most recognised column names.
        best, best_hits = None, 0
        for tr in rows:
            cells = tr.find_all(["th", "td"])
            hits = sum(1 for c in cells if _norm(c.get_text(" ")) in HEADER_MAP)
            if hits > best_hits:
                best, best_hits = cells, hits
        header_cells = best
        if not header_cells or best_hits < 3:
            continue
        index = {}
        for i, cell in enumerate(header_cells):
            key = HEADER_MAP.get(_norm(cell.get_text(" ")))
            if key and key not in index:
                index[key] = i
        if "nom" in index and "sexe" in index:
            return table, index
    return None, None


def parse_page(html: str) -> list[dict]:
    """Extract all data rows from one Idescat page."""
    soup = BeautifulSoup(html, "html.parser")
    table, index = find_names_table(soup)
    if table is None:
        return []
    body = table.find("tbody") or table
    records = []
    for tr in body.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) <= max(index.values()):
            continue
        get = lambda key: cells[index[key]].get_text(" ", strip=True) if key in index else ""
        name = re.sub(r"\s+", " ", get("nom")).strip()
        if not name or _norm(name) == "nom":
            continue
        pos = get("posicio")
        records.append(
            {
                "posicio": int(pos) if pos.isdigit() else pos,
                "sexe": get("sexe"),
                "nom": name,
                "frequencia": parse_number(get("frequencia")),
                "per_mil": parse_number(get("per_mil")),
                "edat_mitjana": parse_number(get("edat_mitjana")),
                "compost": is_composed(name),
                "num_lletres": count_letters(name),
            }
        )
    return records


def fetch(session: requests.Session, posicio: int, retries: int = 4) -> str:
    params = dict(DEFAULT_PARAMS, posicio=str(posicio))
    for attempt in range(retries):
        try:
            resp = session.get(BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            resp.encoding = resp.encoding or "utf-8"
            return resp.text
        except requests.RequestException as exc:
            wait = 2 ** attempt
            print(f"  posicio={posicio}: {exc} (retrying in {wait}s)", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"Could not fetch posicio={posicio} after {retries} attempts")


def scrape(start: int = 1, delay: float = 1.0, max_pages: int | None = None) -> list[dict]:
    """Walk through every posicio page until no new rows appear."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    all_rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    posicio = start
    page = 0
    while max_pages is None or page < max_pages:
        page += 1
        rows = parse_page(fetch(session, posicio))
        new = [r for r in rows if (r["sexe"], r["nom"]) not in seen]
        for r in new:
            seen.add((r["sexe"], r["nom"]))
        all_rows.extend(new)
        print(f"page {page}: posicio={posicio} rows={len(rows)} new={len(new)} total={len(all_rows)}")
        if not rows or not new:
            break
        # Each page starts at row `posicio`, so advance by the rows it showed.
        posicio += len(rows)
        time.sleep(delay)
    return all_rows


def write_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--output", default="noms_idescat.csv", help="output CSV path")
    parser.add_argument("--start", type=int, default=1, help="first posicio to fetch (default 1)")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds to wait between pages")
    parser.add_argument("--max-pages", type=int, default=None, help="stop after N pages (for testing)")
    args = parser.parse_args(argv)

    rows = scrape(start=args.start, delay=args.delay, max_pages=args.max_pages)
    if not rows:
        print("No rows found. The page layout may have changed.", file=sys.stderr)
        return 1
    write_csv(rows, args.output)
    print(f"Saved {len(rows)} names to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
