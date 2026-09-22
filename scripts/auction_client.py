"""Client for reading vehicle listing data out of pickles.com.au search/detail pages.

Pickles renders listings server-side (Next.js App Router / RSC). A plain HTTP GET
returns full HTML that embeds the complete product JSON inside
`self.__next_f.push([1, "..."])` script chunks (React Server Components flight
data). This module pulls those chunks back out into a JSON string, unescapes
them, and locates each individual product object by scanning for its
`"stockNumber"` key and balancing braces backward to find the object's start.

This deliberately avoids calling the site's internal REST API
(`/api-website/buyer/ms-web-asset-search/...`), which is blocked by
robots.txt — everything here comes from ordinary, robots.txt-permitted page
fetches.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Iterable

import requests

BASE_URL = "https://www.pickles.com.au"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')


def fetch_html(path_or_url: str, *, timeout: float = 20.0, retries: int = 3) -> str:
    """GET a pickles.com.au page and return the raw HTML. `path_or_url` may be
    a full URL or a path starting with '/'."""
    url = path_or_url if path_or_url.startswith("http") else BASE_URL + path_or_url
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_err}")


def _decode_rsc_text(html: str) -> str:
    """Extract and concatenate the decoded string payloads of every
    self.__next_f.push([1, "...")]) chunk in the page."""
    parts = []
    for m in _PUSH_RE.finditer(html):
        try:
            parts.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            continue
    return "".join(parts)


def _find_enclosing_object_start(text: str, anchor_pos: int) -> int | None:
    """Scan backward from anchor_pos to find the '{' that opens the object
    directly containing the key at anchor_pos, by balancing braces.
    Not string-literal-aware, but product fields don't contain literal
    braces, so this holds in practice."""
    depth = 0
    i = anchor_pos - 1
    while i >= 0:
        c = text[i]
        if c == "}":
            depth += 1
        elif c == "{":
            if depth == 0:
                return i
            depth -= 1
        i -= 1
    return None


def extract_products(html: str) -> list[dict]:
    """Return every product object embedded in the page, keyed by stockNumber
    (dedup'd)."""
    text = _decode_rsc_text(html)
    decoder = json.JSONDecoder()
    found: dict[str, dict] = {}
    for m in re.finditer(r'"stockNumber":"(\d+)"', text):
        stock_number = m.group(1)
        if stock_number in found:
            continue
        start = _find_enclosing_object_start(text, m.start())
        if start is None:
            continue
        try:
            obj, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("stockNumber") == stock_number:
            found[stock_number] = obj
    return list(found.values())


def search(path: str, *, query: str = "") -> list[dict]:
    """Fetch a /used/search/... page (optionally with a query string already
    url-encoded) and return the parsed product list."""
    html = fetch_html(path + query)
    return extract_products(html)


def detail_url(product: dict) -> str:
    """Best-effort canonical listing URL for a product, using the site's
    observed /used/details/cars/{year}-{make}-{model}/{stockNumber} pattern."""
    stock = product.get("stockNumber", "")
    year = product.get("year", "")
    make = (product.get("make") or "").lower()
    model = (product.get("model") or "").lower()
    slug = f"{year}-{make}-{model}".replace(" ", "-")
    slug = re.sub(r"-+", "-", slug).strip("-")
    return f"{BASE_URL}/used/details/cars/{slug}/{stock}"
