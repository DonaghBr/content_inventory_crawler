# Content Inventory Crawler

Crawls a Red Hat documentation product page and generates a CSV content inventory with the full heading hierarchy and HTML anchor URLs.

## What It Does

1. Fetches the product landing page (e.g., Red Hat OpenShift AI Self-Managed 3.2)
2. Extracts categories from the page navigation (e.g., "Get started", "Administer", "Deploy")
3. Finds all guide links within each category
4. Fetches each guide and extracts every heading (h1-h6) with its HTML anchor ID
5. Writes a CSV with the hierarchical structure mapped to columns

## Setup

1. Create a directory on your local drive
2. Clone the repo into that directory
3. CD into the code directory
4. Create the python virtual environment below

```bash
python3 -m venv venv
source venv/bin/activate       # macOS/Linux
pip install -r requirements.txt
```

## Usage

5. Go to the product docs splash page and copy the url that you want.
6. Follow usage examples below, depending on your requirements, using the url from your splash page. 

```bash
# Basic usage (output goes to output/<product>_content_inventory.csv)
python crawl_content_inventory.py \
  "https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.2"

# Custom output path
python crawl_content_inventory.py \
  "https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.2" \
  --output output/rhoai_3.2_inventory.csv

# Limit to first 3 guides (for quick testing)
python crawl_content_inventory.py \
  "https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.2" \
  --limit 3

# Adjust delay between page fetches (default: 1 second)
python crawl_content_inventory.py \
  "https://docs.redhat.com/en/documentation/red_hat_ai_inference_server/3.2" \
  --delay 0.5
```

## CSV Output Format

| Column | Source | Example |
|--------|--------|---------|
| Category | Landing page nav grouping | "Administer", "Deploy" |
| Titles | Guide name | "Deploying models" |
| Chapters | h2 headings | "Chapter 2. Deploying models" |
| Sections | h3 headings | "2.3. Deploying models on the model serving platform" |
| Sub-sections | h4 headings | "2.1.1. Hardware profile matching" |
| Sub-sub-sections | h5 headings | (rare) |
| Details | h6 headings | (very rare) |
| Notes | Empty | For manual editorial annotations |
| URL | Full URL with anchor | `https://docs.redhat.com/.../deploying_models#section-id` |

The hierarchy is represented by which column a heading appears in. Empty cells indicate the value is inherited from the row above. A blank row separates each guide.

## Example Output

```
Category,Titles,Chapters,Sections,...,URL
Get started,Getting started with OpenShift AI,,,...,https://docs.redhat.com/.../getting_started
,,Chapter 1. Overview,,...,https://...#overview
,,,1.1. Data science workflow,...,https://...#data_science_workflow
,,,1.2. About this guide,...,https://...#about_this_guide
,,Chapter 2. Logging in to OpenShift AI,,...,https://...#logging-in
,,,2.1. Viewing installed components,...,https://...#viewing-installed-components
,,,,,,
Administer,Creating a workbench,,,...,https://docs.redhat.com/.../creating_a_workbench
...
```

## Filtering

You can filter the crawl output by category, title, or chapter to produce a CSV for just the sections you care about. All filters use case-insensitive substring matching. Multiple values for the same flag are OR'd; filters across different flags are AND'd.

Each filter value requires its own flag. Partial words work — `--category "Admin"` matches "Administer".

```bash
URL="https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.2"

# Single category
python crawl_content_inventory.py "$URL" --category "Get started"

# Multiple categories (each needs its own --category flag)
python crawl_content_inventory.py "$URL" --category "Administer" --category "Develop"

# Specific guide by title
python crawl_content_inventory.py "$URL" --title "Release notes"

# Multiple titles
python crawl_content_inventory.py "$URL" --title "Release notes" --title "workbench"

# Category + title (AND'd — must match both)
python crawl_content_inventory.py "$URL" --category "Administer" --title "workbench"

# Category + chapter (only chapters mentioning "deploying" within "Deploy" guides)
python crawl_content_inventory.py "$URL" --category "Deploy" --chapter "deploying"

# Partial, case-insensitive match
python crawl_content_inventory.py "$URL" --category "admin"
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `base_url` | Product landing page URL (required) | -- |
| `--output`, `-o` | Output CSV file path | `output/<product>_content_inventory.csv` |
| `--limit`, `-l` | Max number of guides to fetch (0 = all) | 0 |
| `--delay` | Seconds between page fetches | 1.0 |
| `--category` | Filter by category (repeatable, case-insensitive substring) | -- |
| `--title` | Filter by guide title (repeatable, case-insensitive substring) | -- |
| `--chapter` | Filter by chapter/h2 heading (repeatable, case-insensitive substring) | -- |

## How It Works

- Uses `requests` + `BeautifulSoup` (no browser or JavaScript rendering needed -- Red Hat docs are server-rendered)
- Landing page categories are extracted from `<h2>` headings and their parent containers
- Guide URLs are converted from `/html/` to `/html-single/` to get the full guide on one page
- Headings are extracted from the `<article>` content area, skipping navigation and footer elements
- Red Hat docs boilerplate text ("Copy linkLink copied to clipboard!") is automatically stripped
