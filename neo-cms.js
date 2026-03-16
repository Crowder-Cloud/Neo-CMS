const manifestPath = "content/index.json";
const nav = document.getElementById("nav");
const content = document.getElementById("content");
const pageTitle = document.getElementById("page-title");
const pageSubtitle = document.getElementById("page-subtitle");
const pageStatus = document.getElementById("page-status");
const siteTitle = document.getElementById("site-title");
const siteTagline = document.getElementById("site-tagline");
const siteFooter = document.getElementById("site-footer");
const webmentions = document.getElementById("webmentions");
const metaDescription = document.querySelector('meta[name="description"]');
const ogTitle = document.querySelector('meta[property="og:title"]');
const ogDescription = document.querySelector('meta[property="og:description"]');
const ogUrl = document.querySelector('meta[property="og:url"]');

let manifest = null;
let pages = [];
const pageCache = new Map();
const pageByRoute = new Map();
const routeConflicts = new Set();
const cacheNamespace = "neo-cms-cache:v1:";

const indieweb = {
  siteUrl: "",
  webmentionEndpoint: "",
  author: { name: "", url: "", photo: "" },
};

const readHeadLink = (rel) => {
  const link = document.querySelector(`link[rel="${rel}"]`);
  return link?.getAttribute("href") || "";
};

const escapeHtml = (input) =>
  String(input ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

const slugify = (text) =>
  text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");

const parseSimpleYaml = (lines) => {
  const data = {};
  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) return;
    const match = trimmed.match(/^([A-Za-z0-9_-]+)\s*:\s*(.*)$/);
    if (!match) return;
    let value = match[2].trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    data[match[1]] = value;
  });
  return data;
};

const toBoolean = (value) => {
  if (typeof value === "boolean") return value;
  if (value == null) return false;
  return ["true", "yes", "1", "on"].includes(String(value).toLowerCase());
};

const toNumber = (value, fallback = 0) => {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const readCache = (key) => {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || typeof data.body !== "string") return null;
    return data;
  } catch (error) {
    return null;
  }
};

const writeCache = (key, value) => {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    // Ignore storage failures (private mode, quota, etc.).
  }
};

const fetchTextWithCache = async (url) => {
  const cacheKey = `${cacheNamespace}${url}`;
  const cached = readCache(cacheKey);
  const headers = {};

  if (cached?.etag) headers["If-None-Match"] = cached.etag;
  if (cached?.lastModified) {
    headers["If-Modified-Since"] = cached.lastModified;
  }

  let response;
  try {
    response = await fetch(url, { cache: "no-store", headers });
  } catch (error) {
    if (cached) return cached.body;
    throw error;
  }

  if (response.status === 304 && cached) return cached.body;

  if (!response.ok) {
    if (cached) return cached.body;
    throw new Error("Missing file");
  }

  const body = await response.text();
  const etag = response.headers.get("ETag") || "";
  const lastModified = response.headers.get("Last-Modified") || "";

  if (etag || lastModified) {
    writeCache(cacheKey, {
      body,
      etag,
      lastModified,
      cachedAt: Date.now(),
    });
  }

  return body;
};

const getNotFoundRoute = () => {
  const fallback = manifest?.site?.notFound || "not-found";
  return String(fallback || "").trim();
};

const parseFrontMatter = (raw) => {
  const normalized = raw.replace(/\r\n/g, "\n");
  const lines = normalized.split("\n");
  if (lines[0]?.trim() !== "---") {
    return { meta: {}, body: normalized };
  }

  const yamlLines = [];
  let endIndex = -1;
  for (let i = 1; i < lines.length; i += 1) {
    if (lines[i].trim() === "---") {
      endIndex = i;
      break;
    }
    yamlLines.push(lines[i]);
  }

  if (endIndex === -1) {
    return { meta: {}, body: normalized };
  }

  return {
    meta: parseSimpleYaml(yamlLines),
    body: lines.slice(endIndex + 1).join("\n"),
  };
};

const parseMarkdown = (raw, options = {}) => {
  const allowHtml = Boolean(options.allowHtml);
  const lines = raw.replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let buffer = [];
  let inCode = false;

  const flushParagraph = () => {
    if (!buffer.length) return;
    const paragraph = buffer.join(" ").trim();
    if (paragraph) {
      blocks.push(`<p>${inlineMarkdown(paragraph)}</p>`);
    }
    buffer = [];
  };

  const inlineMarkdown = (text) => {
    let html = allowHtml ? text : escapeHtml(text);
    html = html.replace(
      /!\[([^\]]*)\]\(([^)]+)\)/g,
      (match, alt, url) =>
        `<img src="${escapeHtml(url)}" alt="${escapeHtml(alt)}" loading="lazy" />`,
    );
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    html = html.replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>',
    );
    return html;
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];

    if (line.startsWith("```")) {
      if (inCode) {
        blocks.push(`<pre><code>${escapeHtml(buffer.join("\n"))}</code></pre>`);
        buffer = [];
        inCode = false;
      } else {
        flushParagraph();
        inCode = true;
        buffer = [];
      }
      continue;
    }

    if (inCode) {
      buffer.push(line);
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      continue;
    }

    if (/^#{1,3}\s/.test(line)) {
      flushParagraph();
      const level = line.match(/^#+/)[0].length;
      blocks.push(
        `<h${level}>${inlineMarkdown(line.replace(/^#{1,3}\s/, ""))}</h${level}>`,
      );
      continue;
    }

    if (/^>\s/.test(line)) {
      flushParagraph();
      blocks.push(
        `<blockquote>${inlineMarkdown(line.replace(/^>\s?/, ""))}</blockquote>`,
      );
      continue;
    }

    if (/^(-|\*|\+)\s+/.test(line)) {
      flushParagraph();
      const items = [line];
      while (i + 1 < lines.length && /^(-|\*|\+)\s+/.test(lines[i + 1])) {
        items.push(lines[i + 1]);
        i += 1;
      }
      const htmlItems = items
        .map(
          (item) =>
            `<li>${inlineMarkdown(item.replace(/^(-|\*|\+)\s+/, ""))}</li>`,
        )
        .join("");
      blocks.push(`<ul>${htmlItems}</ul>`);
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      flushParagraph();
      const items = [line];
      while (i + 1 < lines.length && /^\d+\.\s+/.test(lines[i + 1])) {
        items.push(lines[i + 1]);
        i += 1;
      }
      const htmlItems = items
        .map(
          (item) => `<li>${inlineMarkdown(item.replace(/^\d+\.\s+/, ""))}</li>`,
        )
        .join("");
      blocks.push(`<ol>${htmlItems}</ol>`);
      continue;
    }

    if (/^(-{3,}|\*{3,})$/.test(line.trim())) {
      flushParagraph();
      blocks.push("<hr />");
      continue;
    }

    buffer.push(line.trim());
  }

  if (inCode) {
    blocks.push(`<pre><code>${escapeHtml(buffer.join("\n"))}</code></pre>`);
  } else {
    flushParagraph();
  }

  return blocks.join("");
};

const buildRoute = (file, slug) => {
  const stem = file.replace(/\.md$/i, "");
  const parts = stem.split("/");
  const base = slug || parts[parts.length - 1] || "page";
  if (parts.length > 1) {
    parts[parts.length - 1] = base;
    return parts.join("/");
  }
  return base;
};

const loadPageSource = async (file) => {
  if (pageCache.has(file)) return pageCache.get(file);
  const raw = await fetchTextWithCache(`content/${file}`);
  const { meta, body } = parseFrontMatter(raw);
  const headingMatch = body.match(/^#\s+(.+)$/m);
  const title =
    meta.title || (headingMatch ? headingMatch[1].trim() : "Untitled");
  const page = {
    file,
    raw,
    body,
    meta,
    title,
    description: meta.description || "",
    menu: meta.menu || "",
    slug: meta.slug || "",
    weight: toNumber(meta.weight, 0),
    url: meta.url || "",
    draft: toBoolean(meta.draft),
    allowHtml: toBoolean(meta.allowHtml),
  };
  pageCache.set(file, page);
  return page;
};

const setStatus = (text) => {
  pageStatus.textContent = text;
};

const formatMentionDate = (value) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

const getPageUrl = (page, slug) => {
  if (page?.url) return page.url;
  const origin = window.location.origin;
  const fallbackBase =
    origin === "null" ? "" : `${origin}${window.location.pathname}`;
  const base = indieweb.siteUrl || fallbackBase;
  if (!base) return "";
  const baseUrl = base.replace(/#.*$/, "");
  return `${baseUrl}#${slug}`;
};

const updateMetaTags = (page, slug) => {
  const siteT = manifest?.site?.title || "Neo-CMS";
  const pageT = page?.title;
  document.title = pageT ? `${pageT} | ${siteT}` : siteT;

  const desc = page?.description || manifest?.site?.tagline || "";
  if (metaDescription) metaDescription.setAttribute("content", desc);
  if (ogTitle) ogTitle.setAttribute("content", pageT || siteT);
  if (ogDescription) ogDescription.setAttribute("content", desc);

  if (ogUrl) {
    const url = getPageUrl(page, slug);
    ogUrl.setAttribute("content", url || window.location.href);
  }
};

const renderHCard = () => {
  const card = document.querySelector(".brand-card");
  if (!card) return;
  card.classList.add("h-card");
  if (card.querySelector(".p-name")) return; // idempotency guard
  const { name, url, photo } = indieweb.author;
  if (name || url) {
    const anchor = document.createElement("a");
    anchor.className = "p-name u-url";
    anchor.rel = "me";
    anchor.style.display = "none";
    anchor.setAttribute("aria-hidden", "true");
    anchor.textContent = name;
    anchor.href = url;
    card.appendChild(anchor);
  }
  if (photo) {
    const img = document.createElement("img");
    img.className = "u-photo";
    img.src = photo;
    img.style.display = "none";
    img.setAttribute("aria-hidden", "true");
    card.appendChild(img);
  }
};

const renderHEntry = (html, page, slug) => {
  const title = page?.title || "";
  const url = getPageUrl(page, slug) || "";
  const date = page?.meta?.date || "";
  const dateAttr =
    date && /^\d{4}-\d{2}-\d{2}/.test(date)
      ? `<time class="dt-published" datetime="${escapeHtml(date)}" style="display:none" aria-hidden="true"></time>`
      : "";
  return `<div class="h-entry"><span class="p-name" style="display:none" aria-hidden="true">${escapeHtml(title)}</span><a class="u-url" href="${escapeHtml(url)}" style="display:none" aria-hidden="true"></a>${dateAttr}<div class="e-content">${html}</div></div>`;
};

const getMentionType = (mention) => {
  const property = mention["wm-property"];
  const map = {
    "like-of": "Like",
    "repost-of": "Repost",
    "bookmark-of": "Bookmark",
    "in-reply-to": "Reply",
    "mention-of": "Mention",
  };
  return map[property] || "Mention";
};

const getMentionBody = (mention) => {
  const property = mention["wm-property"];
  const actionMap = {
    "like-of": "liked this.",
    "repost-of": "reposted this.",
    "bookmark-of": "bookmarked this.",
    "in-reply-to": "replied:",
    "mention-of": "mentioned this.",
  };
  return (
    mention.content?.text || mention.content?.html || actionMap[property] || ""
  );
};

const renderWebmentions = (mentions, targetUrl) => {
  if (!webmentions) return;
  if (!indieweb.webmentionEndpoint) {
    webmentions.innerHTML = `
      <h2>Webmentions</h2>
      <p class="webmentions-summary">
        Webmentions are disabled until you set a webmention endpoint.
      </p>
    `;
    return;
  }
  const count = mentions.length;
  if (!count) {
    webmentions.innerHTML = `
      <h2>Webmentions</h2>
      <p class="webmentions-summary">
        No webmentions yet. When another site links to ${escapeHtml(
          targetUrl,
        )}, it will show up here.
      </p>
    `;
    return;
  }
  const items = mentions
    .map((mention) => {
      const author = mention.author || {};
      const authorName =
        author.name || author.url || mention.url || "Anonymous";
      const authorUrl = author.url || mention.url || "#";
      const body = getMentionBody(mention);
      const date =
        formatMentionDate(mention.published) ||
        formatMentionDate(mention["wm-received"]);
      return `
        <li class="webmention-item">
          <div class="webmention-meta">${getMentionType(mention)}${
            date ? ` · ${date}` : ""
          }</div>
          <div class="webmention-body">
            <a href="${escapeHtml(authorUrl)}" target="_blank" rel="noopener">
              ${escapeHtml(authorName)}
            </a>
            ${body ? ` - ${escapeHtml(body)}` : ""}
          </div>
        </li>
      `;
    })
    .join("");
  webmentions.innerHTML = `
    <h2>Webmentions</h2>
    <p class="webmentions-summary">
      ${count} mention${count === 1 ? "" : "s"} for ${escapeHtml(targetUrl)}.
    </p>
    <ul class="webmention-list">${items}</ul>
  `;
};

const loadWebmentions = async (page, slug) => {
  if (!webmentions) return;
  const targetUrl = getPageUrl(page, slug);
  if (!targetUrl) {
    webmentions.innerHTML = `
      <h2>Webmentions</h2>
      <p class="webmentions-summary">
        Webmentions are unavailable on local previews.
      </p>
    `;
    return;
  }
  if (!indieweb.webmentionEndpoint) {
    renderWebmentions([], targetUrl);
    return;
  }
  webmentions.innerHTML = `
    <h2>Webmentions</h2>
    <p class="webmentions-summary">Loading webmentions...</p>
  `;
  try {
    const apiUrl = `https://webmention.io/api/mentions.jf2?target=${encodeURIComponent(
      targetUrl,
    )}`;
    const response = await fetch(apiUrl, { cache: "no-store" });
    if (!response.ok) throw new Error("Webmention request failed");
    const data = await response.json();
    const mentions = (data.children || []).slice().sort((a, b) => {
      const dateA = new Date(a.published || a["wm-received"] || 0);
      const dateB = new Date(b.published || b["wm-received"] || 0);
      return dateB - dateA;
    });
    renderWebmentions(mentions, targetUrl);
  } catch (error) {
    webmentions.innerHTML = `
      <h2>Webmentions</h2>
      <p class="webmentions-summary">
        Could not load webmentions for this page.
      </p>
    `;
  }
};

const renderNav = () => {
  nav.innerHTML = "";
  const sections = new Map();
  const order = [];

  pages.forEach((page) => {
    if (page.draft || page.routeConflict) return;
    const menu = page.menu || "Pages";
    if (!sections.has(menu)) {
      sections.set(menu, []);
      order.push(menu);
    }
    sections.get(menu).push(page);
  });

  order.forEach((menu) => {
    const sectionEl = document.createElement("div");
    sectionEl.className = "nav-section";
    sectionEl.innerHTML = `<h3>${menu}</h3>`;

    const links = document.createElement("div");
    links.className = "nav-links";

    const sorted = sections.get(menu).slice().sort((a, b) => {
      if (a.weight !== b.weight) return a.weight - b.weight;
      if (a.order !== b.order) return a.order - b.order;
      return (a.title || a.route).localeCompare(b.title || b.route);
    });

    sorted.forEach((page) => {
      const link = document.createElement("a");
      link.href = `#${page.route}`;
      link.textContent = page.title || page.route;
      link.dataset.slug = page.route;
      links.appendChild(link);
    });

    sectionEl.appendChild(links);
    nav.appendChild(sectionEl);
  });
};

const markActiveLink = (slug) => {
  document.querySelectorAll(".nav-links a").forEach((link) => {
    link.classList.toggle("active", link.dataset.slug === slug);
  });
};

const findPage = (slug) => {
  return pageByRoute.get(slug) || null;
};

const renderEmpty = (message) => {
  content.innerHTML = `<div class="empty">${message}</div>`;
};

const loadPage = async () => {
  if (!manifest) return;
  if (!pages.length) {
    pageTitle.textContent = "No pages";
    pageSubtitle.textContent =
      "Add markdown files to content/ and list them in content/index.json.";
    setStatus("Setup");
    renderEmpty("Add markdown files and refresh to see them here.");
    if (webmentions) {
      webmentions.innerHTML = "";
    }
    return;
  }
  const slug = location.hash.replace("#", "") || pages[0].route;
  let page = findPage(slug);
  const notFoundRoute = getNotFoundRoute();
  const fallbackPage = notFoundRoute ? findPage(notFoundRoute) : null;

  if (!page && fallbackPage && slug !== notFoundRoute) {
    location.hash = `#${notFoundRoute}`;
    return;
  }

  markActiveLink(page ? page.route : slug);
  updateMetaTags(page, slug);

  if (!page) {
    pageTitle.textContent = "Missing page";
    pageSubtitle.textContent =
      "The link you followed does not exist in content/index.json.";
    setStatus("Not found");
    const notFoundLink = fallbackPage
      ? ` or view <a href="#${escapeHtml(
          notFoundRoute,
        )}">the 404 page</a>`
      : "";
    renderEmpty(
      `Add the page back into <code>content/index.json</code> or pick another link${notFoundLink}.`,
    );
    if (webmentions) {
      webmentions.innerHTML = "";
    }
    return;
  }

  currentPage = page;
  pageTitle.textContent = page.title || "Untitled";
  pageSubtitle.textContent = page.description || "";
  setStatus("Loading");

  try {
    const source = await loadPageSource(page.file);
    const html = parseMarkdown(source.body, { allowHtml: source.allowHtml });
    pageTitle.textContent = source.title || pageTitle.textContent;
    updateMetaTags(source, slug);
    content.innerHTML = renderHEntry(html || "<p>Empty page.</p>", source, slug);
    setStatus("Loaded");
    loadWebmentions(page, slug);
  } catch (error) {
    pageTitle.textContent = "Missing file";
    pageSubtitle.textContent = `Could not load content/${page.file}.`;
    setStatus("Error");
    renderEmpty(
      "Create the file or fix the filename in <code>content/index.json</code>.",
    );
    if (webmentions) {
      webmentions.innerHTML = "";
    }
  }
};

const loadPages = async () => {
  pageByRoute.clear();
  pages = [];
  routeConflicts.clear();

  const files = Array.isArray(manifest.files) ? manifest.files : [];
  for (let index = 0; index < files.length; index += 1) {
    const file = files[index];
    try {
      const source = await loadPageSource(file);
      const route = buildRoute(file, source.slug);
      if (source.slug) {
        const normalizedSlug = slugify(source.slug);
        if (normalizedSlug !== source.slug) {
          console.warn(
            `Slug "${source.slug}" in ${file} normalizes to "${normalizedSlug}".`,
          );
        }
        if (source.slug.includes("/")) {
          console.warn(`Slug "${source.slug}" in ${file} contains a "/".`);
        }
      }
      if (pageByRoute.has(route)) {
        routeConflicts.add(route);
        console.warn(
          `Duplicate route "${route}" detected. Only the first instance will appear in navigation.`,
        );
      }
      const page = { ...source, route, order: index };
      if (routeConflicts.has(route)) {
        page.routeConflict = true;
      }
      pages.push(page);
      if (!pageByRoute.has(route)) {
        pageByRoute.set(route, page);
      }
    } catch (error) {
      const route = buildRoute(file, "");
      const fallback = {
        file,
        title: route,
        description: "",
        menu: "",
        slug: "",
        url: "",
        route,
        error: true,
        weight: 0,
        draft: false,
        allowHtml: false,
        order: index,
      };
      pages.push(fallback);
      if (!pageByRoute.has(route)) {
        pageByRoute.set(route, fallback);
      }
    }
  }

  renderNav();
  await loadPage();
};

const loadManifest = async () => {
  try {
    const raw = await fetchTextWithCache(manifestPath);
    manifest = JSON.parse(raw);

    siteTitle.textContent = manifest.site?.title || "Neo-CMS";
    siteTagline.textContent = manifest.site?.tagline || siteTagline.textContent;
    indieweb.webmentionEndpoint =
      readHeadLink("webmention") || indieweb.webmentionEndpoint;
    const siteConfig = manifest.site || {};
    const indiewebConfig = siteConfig.indieweb || {};
    indieweb.siteUrl = siteConfig.url || indieweb.siteUrl;
    indieweb.webmentionEndpoint =
      indiewebConfig.webmentionEndpoint || indieweb.webmentionEndpoint;
    const authorConfig = indiewebConfig.author || {};
    indieweb.author.name  = authorConfig.name  || "";
    indieweb.author.url   = authorConfig.url   || "";
    indieweb.author.photo = authorConfig.photo || "";
    const footerText = manifest.site?.footer || "";
    const sep = footerText ? " " : "";
    siteFooter.innerHTML = `${escapeHtml(footerText)}${sep}<a href="./feed.xml" rel="alternate" type="application/rss+xml">RSS Feed</a>`;
    renderHCard();
    await loadPages();
  } catch (error) {
    pageTitle.textContent = "Manifest missing";
    pageSubtitle.textContent =
      "Create content/index.json to map your markdown files.";
    setStatus("Setup");
    renderEmpty(
      "Create <code>content/index.json</code> and point it at markdown files. Use the sample in this repo as a template.",
    );
    indieweb.webmentionEndpoint =
      readHeadLink("webmention") || indieweb.webmentionEndpoint;
  }
};

window.addEventListener("hashchange", loadPage);
loadManifest();
