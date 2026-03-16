---
title: Changelog
slug: changelog
description: Tiny release log.
menu: Collection
---

## 0.2

- Dynamic `<title>` and Open Graph meta tags updated on every navigation
- RSS feed (`feed.xml`) generated at deploy time via `scripts/generate_feed.py`
- Sitemap (`sitemap.xml`) generated at deploy time via `scripts/generate_sitemap.py`
- Microformats2 support: `h-card` on the brand card, `h-entry` wrapping each page
- RSS autodiscovery `<link>` in `<head>` and RSS link in the site footer
- `author` config in `content/index.json` under `indieweb`
- Content linter (`scripts/validate.py`) runs before deploy and fails CI on errors
- CI pipeline updated with validate, generate-feed, and generate-sitemap steps

## 0.1

- Initial structure
- Basic markdown parsing
- Styled layout
- Minimal IndieAuth `rel="me"` identity links
- Webmention.io for inbound mentions
