"""Tests for scripts/generate_sitemap.py."""
import json
import xml.etree.ElementTree as ET
import pytest
from pathlib import Path

import generate_sitemap as gs

FIXTURES = Path(__file__).parent / "fixtures"

# ---------------------------------------------------------------------------
# Pure-function unit tests
# ---------------------------------------------------------------------------

def test_escape_xml_ampersand():
    assert gs.escape_xml("a & b") == "a &amp; b"


def test_escape_xml_angle_brackets():
    assert gs.escape_xml("<foo>") == "&lt;foo&gt;"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_content(tmp_path, files: dict, site_url="https://example.com/", manifest_files=None):
    content = tmp_path / "content"
    content.mkdir()
    for name, text in files.items():
        (content / name).write_text(text, encoding="utf-8")
    if manifest_files is None:
        manifest_files = list(files.keys())
    manifest = {
        "site": {"title": "T", "tagline": "T", "url": site_url},
        "files": manifest_files,
    }
    (content / "index.json").write_text(json.dumps(manifest), encoding="utf-8")
    return content


def _run(tmp_path, monkeypatch, content):
    output = tmp_path / "sitemap.xml"
    monkeypatch.setattr(gs, "CONTENT", content)
    monkeypatch.setattr(gs, "OUTPUT", output)
    gs.main()
    return output


# ---------------------------------------------------------------------------
# main() integration tests
# ---------------------------------------------------------------------------

def test_main_produces_valid_xml(tmp_path, monkeypatch):
    content = _make_content(tmp_path, {
        "home.md": "---\ntitle: Home\nslug: home\n---\nBody.",
        "post.md": "---\ntitle: Post\nslug: post\ndate: 2024-06-15\n---\nContent.",
    })
    output = _run(tmp_path, monkeypatch, content)
    ET.fromstring(output.read_text(encoding="utf-8"))  # raises if malformed


def test_main_contains_urlset(tmp_path, monkeypatch):
    content = _make_content(tmp_path, {
        "home.md": "---\ntitle: Home\nslug: home\n---\nBody.",
    })
    output = _run(tmp_path, monkeypatch, content)
    assert "<urlset" in output.read_text(encoding="utf-8")


def test_main_url_uses_site_url(tmp_path, monkeypatch):
    content = _make_content(tmp_path, {
        "page.md": "---\ntitle: Page\nslug: page\n---\nBody.",
    }, site_url="https://mysite.com/")
    output = _run(tmp_path, monkeypatch, content)
    xml = output.read_text(encoding="utf-8")
    assert "https://mysite.com#page" in xml


def test_main_url_contains_slug(tmp_path, monkeypatch):
    content = _make_content(tmp_path, {
        "about.md": "---\ntitle: About\nslug: about\n---\nBody.",
    })
    output = _run(tmp_path, monkeypatch, content)
    assert "#about" in output.read_text(encoding="utf-8")


def test_main_lastmod_uses_date_when_present(tmp_path, monkeypatch):
    content = _make_content(tmp_path, {
        "post.md": "---\ntitle: Post\nslug: post\ndate: 2024-06-15\n---\nContent.",
    })
    output = _run(tmp_path, monkeypatch, content)
    assert "2024-06-15" in output.read_text(encoding="utf-8")


def test_main_lastmod_falls_back_to_today(tmp_path, monkeypatch):
    """Pages without a date should use today's date as lastmod."""
    from datetime import date
    today = date.today().isoformat()
    content = _make_content(tmp_path, {
        "home.md": "---\ntitle: Home\nslug: home\n---\nBody.",
    })
    output = _run(tmp_path, monkeypatch, content)
    assert today in output.read_text(encoding="utf-8")


def test_main_excludes_drafts(tmp_path, monkeypatch, capsys):
    content = _make_content(tmp_path, {
        "draft.md": "---\ntitle: Draft\nslug: draft\ndraft: true\n---\nHidden.",
        "pub.md": "---\ntitle: Published\nslug: pub\n---\nVisible.",
    })
    output = _run(tmp_path, monkeypatch, content)
    xml = output.read_text(encoding="utf-8")
    assert "#draft" not in xml
    assert "#pub" in xml
    out = capsys.readouterr().out
    assert "1 URL(s)" in out


def test_main_correct_url_count(tmp_path, monkeypatch, capsys):
    content = _make_content(tmp_path, {
        "a.md": "---\ntitle: A\nslug: a\n---\n",
        "b.md": "---\ntitle: B\nslug: b\n---\n",
        "c.md": "---\ntitle: C\nslug: c\n---\n",
    })
    _run(tmp_path, monkeypatch, content)
    out = capsys.readouterr().out
    assert "3 URL(s)" in out


def test_main_missing_site_url_exits(tmp_path, monkeypatch):
    content = tmp_path / "content"
    content.mkdir()
    (content / "page.md").write_text("---\ntitle: P\nslug: p\n---\n", encoding="utf-8")
    manifest = {"site": {"url": ""}, "files": ["page.md"]}
    (content / "index.json").write_text(json.dumps(manifest), encoding="utf-8")

    output = tmp_path / "sitemap.xml"
    monkeypatch.setattr(gs, "CONTENT", content)
    monkeypatch.setattr(gs, "OUTPUT", output)

    with pytest.raises(SystemExit) as exc_info:
        gs.main()
    assert exc_info.value.code == 1


def test_main_slug_derived_from_filename_when_missing(tmp_path, monkeypatch):
    """If front matter has no slug, the filename (minus .md) is used."""
    content = _make_content(tmp_path, {
        "my-page.md": "---\ntitle: My Page\n---\nBody.",
    })
    output = _run(tmp_path, monkeypatch, content)
    assert "#my-page" in output.read_text(encoding="utf-8")
