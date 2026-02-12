# Content Inventory Crawler

Crawls a Red Hat documentation product page and generates a CSV content inventory with the full heading hierarchy and HTML anchor URLs.

## What It Does

1. Fetches the product landing page (e.g., Red Hat OpenShift AI Self-Managed 3.2)
2. Extracts categories from the page navigation (e.g., "Get started", "Administer", "Deploy")
3. Finds all guide links within each category
4. Fetches each guide and extracts every heading (h1-h6) with its HTML anchor ID
5. Writes a CSV with the hierarchical structure mapped to columns
6. To view the CSV, just upload in your Google Drive, and open it in Google Sheets

## Setup

```bash
python -m venv venv
source venv/bin/activate       # macOS/Linux
pip install -r requirements.txt
```

## Usage

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
## CSV in Output folder - open in Google Sheets
For best results to view the CSV file, upload the CSV file from the 'output' directory to Google Drive and open using the Google Sheets app. 
 
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

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `base_url` | Product landing page URL (required) | -- |
| `--output`, `-o` | Output CSV file path | `output/<product>_content_inventory.csv` |
| `--limit`, `-l` | Max number of guides to fetch (0 = all) | 0 |
| `--delay` | Seconds between page fetches | 1.0 |

## How It Works

- Uses `requests` + `BeautifulSoup` (no browser or JavaScript rendering needed -- Red Hat docs are server-rendered)
- Landing page categories are extracted from `<h2>` headings and their parent containers
- Guide URLs are converted from `/html/` to `/html-single/` to get the full guide on one page
- Headings are extracted from the `<article>` content area, skipping navigation and footer elements
- Red Hat docs boilerplate text ("Copy linkLink copied to clipboard!") is automatically stripped
