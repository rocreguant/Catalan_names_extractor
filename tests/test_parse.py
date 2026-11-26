"""Offline tests for the parser, using a small HTML sample shaped like the Idescat table.

The sample is hand-written from a screenshot of the page, not a saved copy of it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrape_names import count_letters, is_composed, parse_number, parse_page  # noqa: E402

SAMPLE = """
<html><body>
<table>
  <caption>Noms de la població. Catalunya. 2025</caption>
  <thead>
    <tr><th>Pos. ⇅</th><th>Sexe ⇅</th><th>Nom ⇅</th>
        <th>Rànquing freqüència</th><th>‰</th><th>Edat mitjana</th></tr>
  </thead>
  <tbody>
    <tr><td>04958</td><td>H</td><td><a href="#">SANTIAGO MANUEL</a></td><td>75</td><td>0,00</td><td>44,6</td></tr>
    <tr><td>04958</td><td>D</td><td><a href="#">SARA VALENTINA</a></td><td>75</td><td>0,00</td><td>15,9</td></tr>
    <tr><td>04958</td><td>D</td><td><a href="#">SILVERIA</a></td><td>75</td><td>0,00</td><td>70,2</td></tr>
    <tr><td>00001</td><td>H</td><td><a href="#">ANTONIO</a></td><td>1.234</td><td>12,34</td><td>55,0</td></tr>
  </tbody>
</table>
</body></html>
"""


def test_parse_page():
    rows = parse_page(SAMPLE)
    assert len(rows) == 4
    first = rows[0]
    assert first["posicio"] == 4958
    assert first["sexe"] == "H"
    assert first["nom"] == "SANTIAGO MANUEL"
    assert first["frequencia"] == 75
    assert first["per_mil"] == 0.0
    assert first["edat_mitjana"] == 44.6
    assert first["compost"] is True
    assert first["num_lletres"] == 14
    assert rows[2]["compost"] is False
    assert rows[3]["frequencia"] == 1234


def test_helpers():
    assert parse_number("1.234") == 1234
    assert parse_number("44,6") == 44.6
    assert parse_number("") is None
    assert is_composed("ANA ROSA")
    assert is_composed("JOAN-MARC")
    assert not is_composed("PAU")
    assert count_letters("ANA ROSA") == 7
    assert count_letters("MARIA DELS ÀNGELS") == 15
    assert count_letters("GEMMA·L") == 6


def test_slash_spellings():
    from scrape_names import add_wiktionary_flag

    assert count_letters("MARIA/MARÍA") == 5
    assert count_letters("MARIA TERESA/MARÍA TERESA") == 11
    assert not is_composed("MARIA/MARÍA")
    assert is_composed("MARIA TERESA/MARÍA TERESA")

    rows = [{"nom": "MARIA/MARÍA"}, {"nom": "ELENA/HELENA"}, {"nom": "PAU/POL"}]
    add_wiktionary_flag(rows, {"maria", "helena"})
    assert [r["a_viccionari"] for r in rows] == [True, True, False]


def test_no_table():
    assert parse_page("<html><body><p>res</p></body></html>") == []


WIKITEXT = """
Aquesta és una llista de noms propis.
== M ==
* [[Martí]]
* [[Maso]]
* [[Ana]]
* [[Rosa]]
* [[Màxim]]
* [[Maximilià]]
* [[Marcel·la]]
* [[Joan Marc|Joan-Marc]]
* [[Categoria:Noms]]
"""


def test_wiktionary_matching():
    from scrape_names import add_wiktionary_flag, normalize_name, parse_wiktionary_wikitext

    names = parse_wiktionary_wikitext(WIKITEXT)
    assert "marti" in names and "maxim" in names and "marcella" in names
    assert not any("categoria" in n for n in names)
    assert normalize_name("MARCEL·LA") == normalize_name("Marcel.la") == "marcella"

    rows = [{"nom": n} for n in [
        "MARTÍ", "MARTI", "MAXIMILIA", "JOAN MARC", "SANTIAGO MANUEL", "MARCEL.LA",
        "ANA ROSA", "ANA VALENTINA", "MARTÍ-MÀXIM",
    ]]
    add_wiktionary_flag(rows, names)
    assert [r["a_viccionari"] for r in rows] == [True, True, True, True, False, True, True, False, True]


def _page(names):
    rows = "".join(f"<tr><td>{i}</td><td>H</td><td>{n}</td><td>9</td><td>0,1</td><td>40,0</td></tr>"
                   for i, n in enumerate(names))
    return ("<table><thead><tr><th>Pos.</th><th>Sexe</th><th>Nom</th><th>Rànquing freqüència</th>"
            f"<th>‰</th><th>Edat mitjana</th></tr></thead><tbody>{rows}</tbody></table>")


def test_scrape_starts_at_zero_and_stops_after_empty_pages():
    from scrape_names import scrape

    pages = {0: _page(["A", "B"]), 2: _page(["C", "D"]), 4: None, 6: _page(["E"]), 7: "<p></p>", 8: "<p></p>"}
    calls = []

    def fake_fetch(pos):
        calls.append(pos)
        return pages.get(pos, "<p></p>")

    rows = scrape(start=0, delay=0, page_size=2, fetch_page=fake_fetch)
    assert [r["nom"] for r in rows] == ["A", "B", "C", "D", "E"]
    # 4 fails and is skipped, 7 and 8 are empty -> stop
    assert calls == [0, 2, 4, 6, 7, 8]
