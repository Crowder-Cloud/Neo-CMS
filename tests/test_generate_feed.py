"""Tests for scripts/generate_feed.py."""
import json
import xml.etree.ElementTree as ET
import pytest
from pathlib import Path

import generate_feed as gf

FIXTURES = Path(__file__).parent / "fixtures"

# ---------------------------------------------------------------------------
# Pure-function unit tests
# ---------------------------------------------------------------------------

def test_build_rfc822_valid():
    result = gf.build_rfc822("2024-06-15")
    assert result == "Sat, 15 Jun 2024 00:00:00 +0000"


def test_build_rfc822_empty():
    assert gf.build_rfc822("") == ""
    assert gf.build_rfc822(None) == ""


def test_build_rfc822_bad_format():
    assert gf.build_rfc822("15/06/2024") == ""
    assert gf.build_rfc822("not-a-date") == ""


def test_build_rfc822_with_time_suffix():
    """Date strings with a time component should still parse the date portion."""
    result = gf.build_rfc822("2024-01-01T12:00:00")
    assert "01 Jan 2024" in result


def test_escape_xml():
    assert gf.escape_xml("a & b") == "a &amp; b"
    assert gf.escape_xml("<tag>") == "&lt;tag&gt;"
    assert gf.escape_xml('"quoted"') == "&quot;quoted&quot;"


def test_build_item_url():
    assert gf.build_item_url("https://example.com/", "home") == "https://example.com#home"
    assert gf.build_item_url("https://example.com", "post") == "https://example.com#post"


# ---------------------------------------------------------------------------
# generate_feed() output tests
# ---------------------------------------------------------------------------

MANIFEST = {
    "site": {
        "title": "Test Site",
        "tagline": "A tagline.",
        "url": "https://example.com/",
    }
}

PAGES = [
    {"slug": "home", "title": "Home", "description": "Home page.", "date": "", "body": ""},
    {"slug": "post", "title": "My Post", "description": "A post.", "date": "2024-06-15", "body": "Post body."},
]


def test_generate_feed_is_valid_xml():
    xml = gf.generate_feed(MANIFEST, PAGES)
    ET.fromstring(xml)  # raises if not well-formed


def test_generate_feed_rss_version():
    xml = gf.generate_feed(MANIFEST, PAGES)
    assert 'version="2.0"' in xml


def test_generate_feed_channel_title():
    xml = gf.generate_feed(MANIFEST, PAGES)
    assert "<title>Test Site</title>" in xml


def test_generate_feed_item_count():
    xml = gf.generate_feed(MANIFEST, PAGES)
    assert xml.count("<item>") == 2


def test_generate_feed_item_link():
    xml = gf.generate_feed(MANIFEST, PAGES)
    assert "https://example.com#post" in xml


def test_generate_feed_pub_date_present_when_dated():
    xml = gf.generate_feed(MANIFEST, [PAGES[1]])
    assert "<pubDate>" in xml
    assert "Jun 2024" in xml


def test_generate_feed_no_pub_date_when_undated():
    xml = gf.generate_feed(MANIFEST, [PAGES[0]])
    assert "<pubDate>" not in xml


def test_generate_feed_empty_pages():
    xml = gf.generate_feed(MANIFEST, [])
    ET.fromstring(xml)
    assert "<item>" not in xml


# ---------------------------------------------------------------------------
# main() integration test
# ---------------------------------------------------------------------------

def test_main_generates_feed(tmp_path, monkeypatch, capsys):
    content = tmp_path / "content"
    content.mkdir()
    (content / "home.md").write_text(
        "---\ntitle: Home\nslug: home\n---\nBody.", encoding="utf-8"
    )
    (content / "post.md").write_text(
        "---\ntitle: Post\nslug: post\ndate: 2024-06-15\n---\nContent.", encoding="utf-8"
    )
    manifest = {
        "site": {"title": "T", "tagline": "T", "url": "https://example.com/"},
        "files": ["home.md", "post.md"],
    }
    (content / "index.json").write_text(json.dumps(manifest), encoding="utf-8")

    output = tmp_path / "feed.xml"
    monkeypatch.setattr(gf, "CONTENT", content)
    monkeypatch.setattr(gf, "OUTPUT", output)
    gf.main()

    assert output.exists()
    xml = output.read_text(encoding="utf-8")
    ET.fromstring(xml)
    assert "post" in xml
    assert "home" in xml
    out = capsys.readouterr().out
    assert "2 item(s)" in out


def test_main_excludes_drafts(tmp_path, monkeypatch, capsys):
    content = tmp_path / "content"
    content.mkdir()
    (content / "draft.md").write_text(
        "---\ntitle: Draft\nslug: draft\ndraft: true\n---\nHidden.", encoding="utf-8"
    )
    (content / "pub.md").write_text(
        "---\ntitle: Published\nslug: pub\n---\nVisible.", encoding="utf-8"
    )
    manifest = {
        "site": {"title": "T", "tagline": "T", "url": "https://example.com/"},
        "files": ["draft.md", "pub.md"],
    }
    (content / "index.json").write_text(json.dumps(manifest), encoding="utf-8")

    output = tmp_path / "feed.xml"
    monkeypatch.setattr(gf, "CONTENT", content)
    monkeypatch.setattr(gf, "OUTPUT", output)
    gf.main()

    xml = output.read_text(encoding="utf-8")
    assert "draft" not in xml
    assert "pub" in xml
    out = capsys.readouterr().out
    assert "1 item(s)" in out


def test_main_orders_dated_newest_first(tmp_path, monkeypatch):
    content = tmp_path / "content"
    content.mkdir()
    for slug, date in [("old", "2023-01-01"), ("new", "2024-12-31")]:
        (content / f"{slug}.md").write_text(
            f"---\ntitle: {slug}\nslug: {slug}\ndate: {date}\n---\n", encoding="utf-8"
        )
    manifest = {
        "site": {"url": "https://example.com/"},
        "files": ["old.md", "new.md"],
    }
    (content / "index.json").write_text(json.dumps(manifest), encoding="utf-8")

    output = tmp_path / "feed.xml"
    monkeypatch.setattr(gf, "CONTENT", content)
    monkeypatch.setattr(gf, "OUTPUT", output)
    gf.main()

    xml = output.read_text(encoding="utf-8")
    assert xml.index("#new") < xml.index("#old")
