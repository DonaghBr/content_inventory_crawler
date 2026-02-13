#!/usr/bin/env python
"""
Content Inventory Crawler for Red Hat Documentation.

Crawls a Red Hat docs product landing page, extracts the category structure
and all guide headings with HTML anchors, and produces a CSV content inventory.

Usage:
    python crawl_content_inventory.py \
        "https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.2"

    python crawl_content_inventory.py \
        "https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.2" \
        --output output/rhoai_inventory.csv --limit 3
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Resolve paths relative to this script's directory
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    ),
}

CSV_COLUMNS = [
    "Category",
    "Titles",
    "Chapters",
    "Sections",
    "Sub-sections",
    "Sub-sub-sections",
    "Details",
    "Notes",
    "URL",
]

SKIP_HEADINGS = {
    "legal notice",
    "left navigation",
    "copyright",
    "privacy",
    "red hat legal",
    "about red hat",
    "learn",
    "try, buy, & sell",
    "communities",
}

BOILERPLATE_SUFFIXES = [
    "Copy linkLink copied to clipboard!",
    "Copy linkLink copied to clipboard",
    "Copy link",
    "Link copied",
    "Copied!",
    " to clipboard!",
]


def filter_guides(guides, categories=None, titles=None):
    """Filter guides by category and/or title (case-insensitive substring)."""
    filtered = guides
    if categories:
        cats_lower = [c.lower() for c in categories]
        filtered = [g for g in filtered
                    if any(c in g["category"].lower() for c in cats_lower)]
    if titles:
        titles_lower = [t.lower() for t in titles]
        filtered = [g for g in filtered
                    if any(t in g["title"].lower() for t in titles_lower)]
    return filtered


def filter_headings(headings, chapters=None):
    """Filter headings to only include matching h2 chapters and their children."""
    if not chapters:
        return headings
    chaps_lower = [c.lower() for c in chapters]
    filtered = []
    include_children = False
    for h in headings:
        if h["level"] == 2:
            include_children = any(c in h["text"].lower() for c in chaps_lower)
        if include_children:
            filtered.append(h)
    return filtered


def clean_heading_text(text: str) -> str:
    """Strip Red Hat docs boilerplate suffixes from heading text."""
    text = " ".join(text.split())
    for suffix in BOILERPLATE_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
    return text


def should_skip_heading(text: str) -> bool:
    """Check if a heading should be excluded from the inventory."""
    return text.lower().strip() in SKIP_HEADINGS


def to_html_single(url: str) -> str:
    """Convert /html/ URL to /html-single/ for full-page content."""
    return url.replace("/html/", "/html-single/")


def fetch_landing_page(base_url: str) -> list[dict]:
    """
    Fetch the product landing page and extract categories with guide links.

    Returns a list of dicts: [{category, title, url}, ...]
    """
    base_url = base_url.rstrip("/")
    response = requests.get(base_url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    guides = []
    seen_urls = set()

    for h2 in soup.find_all("h2"):
        category = clean_heading_text(h2.get_text(strip=True))
        if should_skip_heading(category):
            continue

        # Find guide links within the h2's parent container
        parent = h2.parent
        if not parent:
            continue

        links = parent.find_all("a", href=True)
        for link in links:
            href = link.get("href", "")
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue

            absolute_url = urljoin(base_url, href)

            # Only include documentation links
            if "/documentation/" not in absolute_url:
                continue

            # Convert to html-single for full-page fetch
            guide_url = to_html_single(absolute_url)

            # Deduplicate
            if guide_url in seen_urls:
                continue
            seen_urls.add(guide_url)

            title = clean_heading_text(link.get_text(strip=True))
            if not title:
                continue

            guides.append(
                {
                    "category": category,
                    "title": title,
                    "url": guide_url,
                }
            )

    return guides


def find_anchor(h) -> str:
    """Find the best anchor ID for a heading element."""
    anchor = h.get("id", "")
    if not anchor:
        parent = h.parent
        if parent:
            anchor = parent.get("id", "")
    if not anchor:
        inner_a = h.find("a", id=True) or h.find("a", attrs={"name": True})
        if inner_a:
            anchor = inner_a.get("id") or inner_a.get("name", "")
    return anchor


def fetch_guide_headings(url: str) -> list[dict]:
    """
    Fetch a guide page and extract all headings with their anchor IDs.

    Returns a list of dicts: [{level, text, anchor, url}, ...]
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=60)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"  Failed to fetch: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the main content area (Red Hat docs patterns)
    article = None
    for selector in [
        'article[aria-live="polite"]',
        "article[aria-live]",
        "article",
        "main",
    ]:
        article = soup.select_one(selector)
        if article:
            break
    if not article:
        article = soup

    # Iterate all headings in document order
    headings = []
    for h in article.find_all(re.compile(r"^h[1-6]$")):
        text = clean_heading_text(h.get_text(strip=True))
        if not text or should_skip_heading(text):
            continue

        level = int(h.name[1])
        anchor = find_anchor(h)
        heading_url = f"{url}#{anchor}" if anchor else url

        headings.append(
            {
                "level": level,
                "text": text,
                "anchor": anchor,
                "url": heading_url,
            }
        )

    return headings


def hyperlink(url: str, text: str) -> str:
    """Wrap text in a spreadsheet HYPERLINK formula."""
    # Escape double quotes inside the text and URL
    safe_url = url.replace('"', '%22')
    safe_text = text.replace('"', '""')
    return f'=HYPERLINK("{safe_url}","{safe_text}")'


def build_csv_rows(guides: list[dict]) -> list[list[str]]:
    """
    Build CSV rows from guides and their headings.

    Each cell value is wrapped in =HYPERLINK("url","text") so it becomes
    a clickable link when opened in Google Sheets or Excel.

    Heading level to column mapping:
    - h1 -> Titles (col 1) -- skipped in favour of landing page title
    - h2 -> Chapters (col 2)
    - h3 -> Sections (col 3)
    - h4 -> Sub-sections (col 4)
    - h5 -> Sub-sub-sections (col 5)
    - h6 -> Details (col 6)
    """
    rows = []
    prev_category = None

    for guide in guides:
        category = guide["category"]
        title = guide["title"]
        headings = guide.get("headings", [])

        # Show category only on the first guide in each category
        show_category = category if category != prev_category else ""
        prev_category = category

        # Title row for this guide
        row = [""] * len(CSV_COLUMNS)
        if show_category:
            row[0] = show_category
        row[1] = hyperlink(guide["url"], title)
        rows.append(row)

        # Skip h1 (page title) since we have the title from the landing page
        content_headings = [h for h in headings if h["level"] >= 2]

        # Heading rows
        for heading in content_headings:
            row = [""] * len(CSV_COLUMNS)
            level = heading["level"]
            # h2=col 2 (Chapters), h3=col 3 (Sections), h4=col 4, h5=col 5, h6=col 6
            col_index = level
            if col_index < len(CSV_COLUMNS) - 2:  # Leave room for Notes + URL
                row[col_index] = hyperlink(heading["url"], heading["text"])
            rows.append(row)

        # Blank separator row after each guide
        rows.append([""] * len(CSV_COLUMNS))

    return rows


def write_csv(rows: list[list[str]], output_path: Path) -> None:
    """Write rows to a CSV file, creating parent directories if needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        writer.writerows(rows)


def slugify_product(url: str) -> str:
    """Extract a slug from the product URL for the default output filename."""
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    # Find the product name part (after "documentation")
    for i, part in enumerate(parts):
        if part == "documentation" and i + 1 < len(parts):
            return parts[i + 1]
    return parts[-1] if parts else "docs"


def main():
    parser = argparse.ArgumentParser(
        description="Crawl Red Hat docs and generate a content inventory CSV.",
    )
    parser.add_argument(
        "base_url",
        help="Product documentation landing page URL",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output CSV file path (default: output/<product>_content_inventory.csv)",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=0,
        help="Limit number of guides to fetch (0 = all, useful for testing)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between page fetches (default: 1.0)",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=None,
        help="Filter by category (case-insensitive substring, repeatable)",
    )
    parser.add_argument(
        "--title",
        action="append",
        default=None,
        help="Filter by guide title (case-insensitive substring, repeatable)",
    )
    parser.add_argument(
        "--chapter",
        action="append",
        default=None,
        help="Filter by chapter heading (case-insensitive substring, repeatable)",
    )

    args = parser.parse_args()

    # Default output path: output/<product>_content_inventory.csv
    if args.output:
        output_path = Path(args.output)
    else:
        slug = slugify_product(args.base_url)
        output_path = OUTPUT_DIR / f"{slug}_content_inventory.csv"

    print(f"Fetching landing page: {args.base_url}")
    guides = fetch_landing_page(args.base_url)
    print(f"Found {len(guides)} guides across categories")

    # Apply category/title filters before limit
    if args.category or args.title:
        guides = filter_guides(guides, args.category, args.title)
        print(f"Filtered to {len(guides)} guides", end="")
        if args.category:
            print(f" (category: {', '.join(args.category)})", end="")
        if args.title:
            print(f" (title: {', '.join(args.title)})", end="")
        print()

    if args.limit > 0:
        guides = guides[: args.limit]
        print(f"Limited to first {args.limit} guides")

    # Fetch headings for each guide
    for i, guide in enumerate(guides, 1):
        print(f"[{i}/{len(guides)}] {guide['title'][:60]}...")
        guide["headings"] = fetch_guide_headings(guide["url"])
        if args.chapter:
            guide["headings"] = filter_headings(guide["headings"], args.chapter)
        heading_count = len(guide["headings"])
        print(f"  {heading_count} headings extracted")

        if i < len(guides):
            time.sleep(args.delay)

    # Build and write CSV
    rows = build_csv_rows(guides)
    write_csv(rows, output_path)

    total_headings = sum(len(g.get("headings", [])) for g in guides)
    categories = len(set(g["category"] for g in guides))
    print(f"\nDone! Wrote {output_path}")
    print(f"  {categories} categories, {len(guides)} guides, {total_headings} headings")
    print(f"  {len(rows)} CSV rows (including separators)")


if __name__ == "__main__":
    main()
