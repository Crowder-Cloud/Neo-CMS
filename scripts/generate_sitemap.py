#!/usr/bin/env python3
"""Generate sitemap.xml from content pages."""
import json
import re
import sys
from datetime import date
from pathlib import Path

from frontmatter import parse_front_matter, simple_yaml_parse

ROOT = Path(__file__).parent.parent
CONTENT = ROOT / "content"
OUTPUT = ROOT / "sitemap.xml"


def escape_xml(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def main():
    manifest_path = CONTENT / "index.json"
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: could not load manifest: {e}", file=sys.stderr)
        sys.exit(1)

    site_url = manifest.get("site", {}).get("url", "").rstrip("/")
    if not site_url:
        print("ERROR: site.url is empty in content/index.json; cannot generate sitemap.", file=sys.stderr)
        sys.exit(1)

    today = date.today().isoformat()
    files = manifest.get("files", [])
    url_entries = []

    for file in files:
        file_path = CONTENT / file
        try:
            text = file_path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, _ = parse_front_matter(text)
        if meta.get("draft", "").lower() in ("true", "yes", "1", "on"):
            continue
        slug = meta.get("slug", "").strip()
        if not slug:
            slug = re.sub(r'\.md$', '', file.split("/")[-1])
        lastmod = meta.get("date", "").strip()
        if not lastmod or not re.match(r'^\d{4}-\d{2}-\d{2}', lastmod):
            lastmod = today
        loc = escape_xml(f"{site_url}#{slug}")
        url_entries.append(
            f"  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"  </url>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(url_entries) + "\n"
        "</urlset>\n"
    )
    OUTPUT.write_text(xml, encoding="utf-8")
    print(f"Generated {OUTPUT} with {len(url_entries)} URL(s).")


if __name__ == "__main__":
    main()
