"""Tests for scripts/validate.py."""
import json
import pytest
from pathlib import Path

import validate as v

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Pure-function unit tests
# ---------------------------------------------------------------------------

def test_parse_front_matter_basic():
    text = "---\ntitle: Hello\nslug: hello\n---\nBody text."
    meta, body = v.parse_front_matter(text)
    assert meta["title"] == "Hello"
    assert meta["slug"] == "hello"
    assert body.strip() == "Body text."


def test_parse_front_matter_no_fence():
    text = "No front matter here."
    meta, body = v.parse_front_matter(text)
    assert meta == {}
    assert body == text


def test_parse_front_matter_unclosed_fence():
    text = "---\ntitle: Hello\nNo closing fence."
    meta, body = v.parse_front_matter(text)
    assert meta == {}


def test_simple_yaml_parse_strips_quotes():
    lines = ['title: "Quoted Title"', "slug: 'single-quoted'"]
    data = v.simple_yaml_parse(lines)
    assert data["title"] == "Quoted Title"
    assert data["slug"] == "single-quoted"


def test_simple_yaml_parse_ignores_comments():
    lines = ["# a comment", "title: Real"]
    data = v.simple_yaml_parse(lines)
    assert "title" in data
    assert "#" not in str(data)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_content(tmp_path, files: dict, manifest_files=None):
    """Write content files and index.json under tmp_path/content."""
    content = tmp_path / "content"
    content.mkdir()
    for name, text in files.items():
        (content / name).write_text(text, encoding="utf-8")
    if manifest_files is None:
        manifest_files = list(files.keys())
    manifest = {"site": {"url": "https://example.com/"}, "files": manifest_files}
    (content / "index.json").write_text(json.dumps(manifest), encoding="utf-8")
    return content


def _run_main(monkeypatch, content_path):
    """Patch CONTENT and call main(), returning the SystemExit code (0 = pass)."""
    monkeypatch.setattr(v, "CONTENT", content_path)
    with pytest.raises(SystemExit) as exc_info:
        v.main()
    return exc_info.value.code


def _run_main_ok(monkeypatch, content_path, capsys):
    """Expect main() to succeed (no SystemExit)."""
    monkeypatch.setattr(v, "CONTENT", content_path)
    v.main()  # should not raise


# ---------------------------------------------------------------------------
# main() integration tests — valid content
# ---------------------------------------------------------------------------

VALID_HOME = "---\ntitle: Home\nslug: home\n---\nBody."
VALID_POST = "---\ntitle: Post\nslug: my-post\ndate: 2024-01-15\n---\nContent."


def test_valid_content_passes(tmp_path, monkeypatch, capsys):
    content = _make_content(tmp_path, {"home.md": VALID_HOME, "post.md": VALID_POST})
    _run_main_ok(monkeypatch, content, capsys)
    out = capsys.readouterr().out
    assert "Validation passed" in out
    assert "2 file(s)" in out


def test_valid_content_from_fixtures(monkeypatch, capsys):
    """Smoke-test against the committed fixture files."""
    monkeypatch.setattr(v, "CONTENT", FIXTURES)
    v.main()
    out = capsys.readouterr().out
    assert "Validation passed" in out


# ---------------------------------------------------------------------------
# main() integration tests — invalid content
# ---------------------------------------------------------------------------

def test_missing_title_fails(tmp_path, monkeypatch):
    content = _make_content(tmp_path, {"page.md": "---\nslug: page\n---\nBody."})
    code = _run_main(monkeypatch, content)
    assert code == 1


def test_missing_slug_fails(tmp_path, monkeypatch):
    content = _make_content(tmp_path, {"page.md": "---\ntitle: Page\n---\nBody."})
    code = _run_main(monkeypatch, content)
    assert code == 1


def test_bad_date_format_fails(tmp_path, monkeypatch):
    bad = "---\ntitle: Page\nslug: page\ndate: 15/01/2024\n---\nBody."
    content = _make_content(tmp_path, {"page.md": bad})
    code = _run_main(monkeypatch, content)
    assert code == 1


def test_duplicate_slugs_fail(tmp_path, monkeypatch):
    same_slug = "---\ntitle: {t}\nslug: same-slug\n---\nBody."
    content = _make_content(tmp_path, {
        "a.md": same_slug.format(t="A"),
        "b.md": same_slug.format(t="B"),
    })
    code = _run_main(monkeypatch, content)
    assert code == 1


def test_missing_listed_file_fails(tmp_path, monkeypatch):
    content = _make_content(tmp_path, {"home.md": VALID_HOME},
                            manifest_files=["home.md", "ghost.md"])
    code = _run_main(monkeypatch, content)
    assert code == 1


def test_valid_date_passes(tmp_path, monkeypatch, capsys):
    page = "---\ntitle: Page\nslug: page\ndate: 2024-12-31\n---\nBody."
    content = _make_content(tmp_path, {"page.md": page})
    _run_main_ok(monkeypatch, content, capsys)


def test_date_with_time_suffix_passes(tmp_path, monkeypatch, capsys):
    """Date values like '2024-01-15T00:00:00' should pass (starts with YYYY-MM-DD)."""
    page = "---\ntitle: Page\nslug: page\ndate: 2024-01-15T00:00:00\n---\nBody."
    content = _make_content(tmp_path, {"page.md": page})
    _run_main_ok(monkeypatch, content, capsys)
