#!/usr/bin/env python3
"""Content linter — exits 1 on any error to block CI deployment."""
import json
import re
import sys
from pathlib import Path

from frontmatter import parse_front_matter, simple_yaml_parse

ROOT = Path(__file__).parent.parent
CONTENT = ROOT / "content"


def main():
    errors = []

    # 1. Validate manifest JSON
    manifest_path = CONTENT / "index.json"
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {manifest_path} not found", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: {manifest_path} is invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    files = manifest.get("files", [])
    if not isinstance(files, list):
        errors.append("manifest 'files' must be an array")
        files = []

    slugs_seen = {}

    for file in files:
        file_path = CONTENT / file

        # 2. Each file must exist
        if not file_path.exists():
            errors.append(f"{file}: file not found at {file_path}")
            continue

        try:
            text = file_path.read_text(encoding="utf-8")
        except OSError as e:
            errors.append(f"{file}: could not read: {e}")
            continue

        meta, _ = parse_front_matter(text)

        # 3. Non-empty title and slug
        title = meta.get("title", "").strip()
        slug = meta.get("slug", "").strip()

        if not title:
            errors.append(f"{file}: missing or empty 'title' in front matter")
        if not slug:
            errors.append(f"{file}: missing or empty 'slug' in front matter")

        # 4. Date format
        date = meta.get("date", "").strip()
        if date and not re.match(r'^\d{4}-\d{2}-\d{2}', date):
            errors.append(f"{file}: 'date' value {date!r} does not match YYYY-MM-DD")

        # 5. No duplicate slugs
        if slug:
            if slug in slugs_seen:
                errors.append(
                    f"{file}: duplicate slug {slug!r} (first seen in {slugs_seen[slug]})"
                )
            else:
                slugs_seen[slug] = file

    if errors:
        print("Validation errors:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    print(f"Validation passed: {len(files)} file(s) checked.")


if __name__ == "__main__":
    main()
