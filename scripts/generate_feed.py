#!/usr/bin/env python3
"""Generate RSS 2.0 feed.xml from content pages."""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from frontmatter import parse_front_matter, simple_yaml_parse

ROOT = Path(__file__).parent.parent
CONTENT = ROOT / "content"
OUTPUT = ROOT / "feed.xml"

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def build_rfc822(date_str):
    """Convert YYYY-MM-DD to RFC 822 format, or return '' on failure."""
    if not date_str or not re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
        return ""
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return (
            f"{DAYS[d.weekday()]}, {d.day:02d} {MONTHS[d.month - 1]} {d.year} "
            f"00:00:00 +0000"
        )
    except ValueError:
        return ""


def build_item_url(site_url, slug):
    return f"{site_url.rstrip('/')}#{slug}"


def escape_xml(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_feed(manifest, pages):
    site = manifest.get("site", {})
    site_url = site.get("url", "").rstrip("/")
    title = escape_xml(site.get("title", "Neo-CMS"))
    tagline = escape_xml(site.get("tagline", ""))
    now_rfc822 = (
        datetime.now(tz=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    )

    items_xml = []
    for page in pages:
        slug = page["slug"]
        item_url = escape_xml(build_item_url(site_url, slug))
        item_title = escape_xml(page.get("title", slug))
        item_desc = escape_xml(page.get("description", ""))
        pub_date = build_rfc822(page.get("date", ""))
        pub_date_xml = f"    <pubDate>{pub_date}</pubDate>\n" if pub_date else ""
        body = page.get("body", "")
        items_xml.append(
            f"  <item>\n"
            f"    <title>{item_title}</title>\n"
            f"    <link>{item_url}</link>\n"
            f"    <guid isPermaLink=\"true\">{item_url}</guid>\n"
            f"{pub_date_xml}"
            f"    <description>{item_desc}</description>\n"
            f"    <content:encoded><![CDATA[{body}]]></content:encoded>\n"
            f"  </item>"
        )

    items_str = "\n".join(items_xml)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "<channel>\n"
        f"  <title>{title}</title>\n"
        f"  <link>{escape_xml(site_url)}/</link>\n"
        f"  <description>{tagline}</description>\n"
        f"  <lastBuildDate>{now_rfc822}</lastBuildDate>\n"
        f"  <atom:link href=\"{escape_xml(site_url)}/feed.xml\" "
        f'rel="self" type="application/rss+xml"/>\n'
        f"{items_str}\n"
        "</channel>\n"
        "</rss>\n"
    )


def main():
    manifest_path = CONTENT / "index.json"
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: could not load manifest: {e}", file=sys.stderr)
        sys.exit(1)

    site_url = manifest.get("site", {}).get("url", "")
    if not site_url:
        print("WARNING: site.url is empty in content/index.json; feed URLs will be incomplete.", file=sys.stderr)

    files = manifest.get("files", [])
    pages = []
    for file in files:
        file_path = CONTENT / file
        try:
            text = file_path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = parse_front_matter(text)
        if meta.get("draft", "").lower() in ("true", "yes", "1", "on"):
            continue
        slug = meta.get("slug", "").strip()
        if not slug:
            # derive slug from filename
            slug = re.sub(r'\.md$', '', file.split("/")[-1])
        pages.append({
            "slug": slug,
            "title": meta.get("title", slug),
            "description": meta.get("description", ""),
            "date": meta.get("date", ""),
            "body": body.strip(),
        })

    # Sort dated pages newest first, undated pages last
    dated = [p for p in pages if p["date"]]
    undated = [p for p in pages if not p["date"]]
    dated.sort(key=lambda p: p["date"], reverse=True)
    pages = dated + undated

    xml = generate_feed(manifest, pages)
    OUTPUT.write_text(xml, encoding="utf-8")
    print(f"Generated {OUTPUT} with {len(pages)} item(s).")


if __name__ == "__main__":
    main()
