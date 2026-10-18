"""Regressionstests für den Render-Kern (``md_render.py``).

Deckt die rein funktionalen Teile ab, die in den Code-Reviews als fehlend
benannt wurden: Frontmatter (inklusive der 1.3.0-Regression), Block-Skalare
(1.4.3-Regression), Wiki-Links/Bild-Embed sowie die Anker-Kompatibilität.
"""

import re

import pytest

from md_render import (
    _parse_frontmatter_pairs,
    markdown_to_html,
    strip_frontmatter,
)


class TestStripFrontmatter:
    def test_no_frontmatter_is_unchanged(self):
        text = "# Titel\n\nText\n"
        assert strip_frontmatter(text) == ("", text)

    def test_standard_yaml_frontmatter(self):
        fm, content = strip_frontmatter("---\ntitle: X\nautor: Y\n---\n# Titel\n")
        assert fm == "title: X\nautor: Y"
        assert content == "# Titel\n"

    def test_bare_fence_at_start_is_not_unwrapped(self):
        # Regression 1.3.0: Ein nackter ```-Fence am Dokumentanfang darf NICHT
        # als Markdown-Huelle entpackt werden, sonst wird Code als Markdown
        # gerendert und Links/Bilder werden lebendig.
        text = "```\ncode\n```\n# Titel\n"
        assert strip_frontmatter(text) == ("", text)

    def test_markdown_wrapper_is_unwrapped(self):
        fm, content = strip_frontmatter("```markdown\n# Titel\n```\n")
        assert fm == ""
        assert content == "# Titel"

    def test_markdown_wrapper_with_frontmatter(self):
        fm, content = strip_frontmatter(
            "```markdown\n---\ntitle: X\n---\n# Titel\n```\n"
        )
        assert fm == "title: X"
        assert content == "# Titel"


class TestParseFrontmatterPairs:
    def test_plain_scalar(self):
        assert _parse_frontmatter_pairs("key: wert") == [("key", "wert")]

    def test_folded_block_scalar(self):
        # Regression 1.4.3: "description: >" muss die eingerueckten Folgezeilen
        # zu einem Wert falten, nicht nur den Indikator ">" zeigen.
        fm = "description: >\n  Zeile eins\n  Zeile zwei"
        assert _parse_frontmatter_pairs(fm) == [
            ("description", "Zeile eins Zeile zwei")
        ]

    def test_literal_block_scalar_keeps_newlines(self):
        fm = "body: |\n  a\n  b"
        assert _parse_frontmatter_pairs(fm) == [("body", "a\nb")]

    def test_list_under_key_is_joined(self):
        fm = "tags:\n  - a\n  - b"
        assert _parse_frontmatter_pairs(fm) == [("tags", "a, b")]

    def test_comments_and_blank_lines_are_ignored(self):
        fm = "# Kommentar\n\nkey: wert"
        assert _parse_frontmatter_pairs(fm) == [("key", "wert")]


class TestWikiLinksAndEmbeds:
    def test_wikilink_adds_md_and_slugified_anchor(self):
        html = markdown_to_html("[[andere#Abschnitt|Alias]]\n")
        assert 'href="andere.md#abschnitt"' in html
        assert ">Alias</a>" in html

    def test_wikilink_without_extension_uses_filename_as_text(self):
        html = markdown_to_html("[[andere]]\n")
        assert 'href="andere.md"' in html
        assert ">andere</a>" in html

    def test_wikilink_keeps_existing_extension(self):
        html = markdown_to_html("[[andere.md]]\n")
        assert 'href="andere.md"' in html

    def test_wikilink_inside_inline_code_stays_text(self):
        html = markdown_to_html("`[[a.md]]`\n")
        assert "[[a.md]]" in html
        assert 'href="a.md"' not in html

    def test_embed_image(self):
        html = markdown_to_html("![[bild.png]]\n")
        assert 'src="bild.png"' in html
        assert "<img" in html

    def test_embed_non_image_stays_text(self):
        html = markdown_to_html("![[datei.txt]]\n")
        assert "<img" not in html
        assert "![[datei.txt]]" in html

    def test_embed_inside_code_fence_stays_text(self):
        html = markdown_to_html("```\n![[x.png]]\n```\n")
        assert "<img" not in html
        assert "![[x.png]]" in html


@pytest.mark.xfail(
    reason="Bekanntes Problem (Review M3): _slugify erzeugt 'a-b-c', die "
    "toc-Extension vergibt aber 'a_b-c'. Der Wiki-Link-Anker trifft dann nicht.",
    strict=False,
)
def test_wikilink_anchor_matches_heading_id():
    html = markdown_to_html("# a_b c\n\n[[doc.md#a_b c]]\n")
    heading_id = re.search(r'<h1 id="([^"]+)"', html).group(1)
    anchor = re.search(r'href="doc\.md#([^"]+)"', html).group(1)
    assert anchor == heading_id
