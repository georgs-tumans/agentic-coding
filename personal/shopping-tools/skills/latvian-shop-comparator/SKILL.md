---
name: latvian-shop-comparator
description: Find and compare prices for a product across Latvian online stores (salidzini.lv, kurpirkt.lv, 220.lv, rdveikals.lv, 1a.lv and others), check seller ratings and the user's trusted-seller lists, verify stock and price on the product pages, and save a ranked recommendation report with direct product links. Use whenever the user wants the best price for something in Latvia, asks where to buy a product in Latvia, wants to compare Latvian shops or check whether a Latvian seller is reputable.
---

# Latvian Shop Comparator Skill

## Purpose

Search Latvian internet stores for a specific product, compare prices across sellers, check seller credibility via ratings and reviews, and produce a ranked recommendation report with direct product links.

## When to Use

Use this skill whenever a user asks to:
- Find the best price for a product in Latvia
- Compare prices across Latvian online stores
- Check if a specific product is available in Latvian shops
- Find reputable sellers for a product in Latvia
- Get a price comparison report for any product in the Latvian market

## Product Identification

Before searching, ensure you have a **precise product identifier**:
- Full product name (e.g., "G.Skill Ripjaws V 32GB F4-3200C16D-32GVK DDR4")
- Model number / SKU / EAN if available
- Key specifications (capacity, type, speed, etc.)

## Questions Before Searching

Before you start searching, ask the user in one message, skipping anything the request already answers, so the run doesn't stop later waiting for an answer:
- **Product details** — clarifying questions if the description is incomplete (see above)
- **Report folder** — where to save the report; suggest `~/Documents/` as the default
- **Delivery** — whether to include delivery in the price comparison, and if so which option (for example the cheapest parcel locker, courier to the door, or free store pickup). By default, prices are compared without delivery

If nobody can answer (for example an unattended run), use the defaults: `~/Documents/` and prices without delivery. Say so in the report.

## Trusted Seller Lists

The user has established trust levels for Latvian sellers. Always respect these tiers:

### Trusted Sellers (prioritize these)
These are sellers the user has bought from multiple times without issues:
- https://www.rdveikals.lv/
- https://www.euronics.lv/
- https://www.1a.lv/
- https://220.lv/lv/
- https://pta.lv/lv/
- https://e-menessaptieka.lv/
- https://www.benu.lv/
- https://internetaptieka.lv/
- https://www.drogas.lv/lv/
- https://balticdata.lv/ (Cloudflare blocks plain `curl`; use playwright-cli)
- https://www.dateks.lv/
- https://www.m79.lv/

### Less Trusted but Viable Sellers
These are acceptable but the user has less confidence:
- https://aio.lv/

### Untrusted / Random Sellers
Avoid unless no other option exists. Flag these clearly in reports. These typically include:
- Sellers with very few reviews (under 50) on salidzini.lv
- Sellers that appear to be dropshippers (no inventory, very long delivery)
- Unknown Estonian or foreign sites unless they offer significantly better value

## Search Methodology

### Step 1: Initial Search via SearXNG
Search for the product using multiple queries:
- Exact product name + "Latvija" or "Latvia"
- Model number / SKU
- Combine with aggregator site filters: `site:salidzini.lv`, `site:kurpirkt.lv`
- Check individual trusted stores: `site:220.lv`, `site:rdveikals.lv`, etc.

### Step 2: Aggregator Sites (Primary Data Source)
Use **playwright-cli** to browse:

**salidzini.lv** — Primary aggregator with seller ratings:
- Navigate to: `https://www.salidzini.lv/cena?q=<product_query>`
- Extract: product name, price, seller name, seller rating, review count, stock level, delivery time, delivery cost, product URL
- Seller rating is available at: `https://www.salidzini.lv/veikals/<seller_domain>`
- Salidzini.lv also marks "Salidzini.lv iesaka veikalu" (recommended by salidzini.lv) — these are positive signals

**kurpirkt.lv** — Secondary aggregator:
- Navigate to: `https://www.kurpirkt.lv/cena.php?q=<product_query>`
- Extract same fields as salidzini.lv
- Note: kurpirkt.lv may have Cloudflare protection; if blocked, rely on salidzini.lv

### Step 3: Direct Product Page Verification
Open the actual product page for the 5-8 cheapest options **plus every seller on the trusted list that carries the product**, even if it is not among the cheapest. Leave shops whose page you didn't open out of the report. On each page verify:
- **Stock status** — is it actually available or out of stock?
- **Current price** — does it match the aggregator listing?
- **Delivery details** — delivery time and cost, and any free-delivery minimum. If the user asked to include delivery, note the cost of the option they chose
- **Purchase button** — if a "Pirkt" (Buy) or "Iegādāt" button is visible, the product is available

#### Price Verification Priority
**Only include prices that you have verified by opening the product page directly.** Aggregator prices (from salidzini.lv or kurpirkt.lv) are considered preliminary and may be stale. The final report must only show prices confirmed by visiting the actual product listing page.

**Exception — Cloudflare-blocked product pages:** If the product page is behind Cloudflare (403) and you cannot verify the price directly, use the price from the aggregator listing but **flag it as "unconfirmed"** in the report. Mark the price cell with an asterisk and add a note.

#### Cloudflare Fallback — Try Structured Data Sources First
Before giving up on a Cloudflare-blocked site, attempt to access its structured data sources:
- **Internal APIs** — Many Latvian e-commerce sites load product data via AJAX/fetch calls. Use `playwright-cli requests` to monitor network traffic when loading the aggregator page, or try common API endpoints like `<domain>/api/product/<id>`, `<domain>/api/catalog/product?sku=<model>`, etc.
- **JSON-LD / Schema.org** — Some sites embed structured product data (price, availability) in JSON-LD format within the HTML. Pages often have several JSON-LD blocks (breadcrumbs, organization, product), so read all of them and use the one with `"@type": "Product"` and its `offers`: `playwright-cli --raw eval "JSON.stringify([...document.querySelectorAll('script[type=\"application/ld+json\"]')].map(s => s.textContent))"`.
- **Page source scraping** — Use `curl -sL` with a realistic User-Agent to fetch the page HTML and grep for price/stock data embedded in `<script>` tags or meta tags.
- **Salidzini.lv seller pages** — Sometimes salidzini.lv itself has cached or mirrored data for shops that are Cloudflare-blocked. Check the salidzini.lv seller page for any price information.

If all structured data approaches fail, fall back to the aggregator price marked as "unconfirmed" and document which sites were Cloudflare-blocked.

### Step 4: Seller Rating Verification
For each seller found, check their salidzini.lv rating page:
- Navigate to: `https://www.salidzini.lv/veikals/<seller_domain>`
- Extract: overall rating (out of 5), total review count, company registration info
- Note sellers with a rating below 3.0, fewer than 50 reviews (potential fake reviews) or registration less than 1 year old; the Filtering Rules decide what happens to them

### Step 5: Cross-Reference Trusted Lists
For each seller found:
- If it's in the **trusted list**, note it prominently in the report
- If it's in the **less trusted list**, mark it "less trusted". The user already accepts these shops, so the rating and review limits don't apply to them
- If it's **neither**, evaluate based on salidzini.lv rating and review count

Then apply the Filtering Rules below.

## Filtering Rules

When deciding which sellers to include in the final report (rules 1–4 decide, the rest only narrow the list):
1. **Include all sellers** from the user's trusted list that carry the product
2. **Exclude sellers** with rating < 3.0 (unless on the trusted or less trusted list)
3. **Exclude sellers** with < 50 reviews (unless on the trusted or less trusted list)
4. **Exclude sellers** that are clearly foreign/dropshipper with no local presence (for example delivery longer than 30 days, no physical store)
5. **Include** every other seller with rating ≥ 3.5 and ≥ 50 reviews, and every less trusted seller that carries the product. Mark sellers with 50–99 reviews as "few reviews" in the report
6. Sellers rated 3.0–3.4 (not on a list) are included only if few other sellers carry the product, and marked "low rating"
7. If many sellers have it, drop the most expensive non-trusted options so the ranking stays readable

Mark sellers not on either list that were registered less than 1 year ago as "new shop". This alone does not exclude them.

## Report Generation

### Report Location
Save the report in the folder the user chose before the search (see Questions Before Searching; default `~/Documents/`). If that folder doesn't exist or isn't writable (for example inside a sandbox), save to the current working directory and say so.

Filename format: `<product_short_name>_comparison_<YYYY-MM-DD>.md`
Example: `gskill_ripjaws_v_32gb_comparison_2026-10-23.md`

### Report Format
The report is a Markdown file built around comparison tables that are easy to scan: one row per shop, short cell values (no sentences inside cells), prices with the € sign, and the number the ranking is sorted by in bold. Put explanations below the tables, not in them.

The template shows the default: prices compared without delivery. If the user asked to include delivery, add a "Total with delivery" row to each recommendation table and a "Total with delivery" column after "Price" in the ranking, using the delivery option they chose. Sort by that total and put it in bold instead of the price.

Use these sections:

```markdown
# <Product Full Name> — Price Comparison Report

**Product:** <full product name with specs>
**Model/SKU:** <model number if available>
**EAN:** <EAN if available>
**Report Date:** <YYYY-MM-DD>
**Data Sources:** salidzini.lv, kurpirkt.lv, direct product page verification
**Delivery:** <not included in prices / included: chosen option>

---

## ⭐ Top Recommendations

### 🥇 #1 Best Value — <shop name>
| Detail | Info |
|--------|------|
| **Price** | **€<price>** |
| **Rating** | ⭐ <rating> / 5.0 |
| **Reviews** | <count> |
| **Stock** | ✅ <stock status> |
| **Delivery** | <time>, <cost> |
| **Product Page** | <direct URL> |

> **Verdict:** <brief explanation of why this is recommended>

### 🥈 #2 <position> — <shop name>
[... same format ...]

---

## 📊 Complete Price Ranking (All Sellers Found)

Sorted by price.

| # | Shop | Price | Rating | Reviews | Stock | Delivery | Your List |
|---|------|-------|--------|---------|-------|----------|-----------|
| 1 | **<shop>** | **€<price>** | <rating> | <count> | <stock> | <time>, <cost> | <trusted/less trusted/neither> |
| ... |

---

## 🔍 Shops Checked but Not Carrying / Could Not Verify

| Shop | Status |
|------|--------|
| **<shop>** | <reason: not found, Cloudflare blocked, etc.> |
| ... |

---

## 🚧 Cloudflare-Blocked Sites

The following sites could not be accessed directly due to Cloudflare protection. Prices listed below are from aggregator sites and marked as **unconfirmed** in the report. Structured data fallbacks were attempted but did not yield verifiable results.

| Shop | Aggregator Price | Fallback Attempted | Confirmed? |
|------|-----------------|-------------------|------------|
| **<shop>** | €<price> | <api/jsonld/curl> | ⚠️ Unconfirmed |
| ... |

---

## 🎯 Final Recommendation

| If you want... | Choose... |
|----------------|-----------|
| **Best overall value** | **<shop>** — <price>, <key reason> |
| **Maximum trust** | **<shop>** — <price>, <key reason> |
| **Absolute cheapest** | **<shop>** — <price>, <caveat if any> |
| **Best rating + availability** | **<shop>** — <price>, <key reason> |

### My top pick: **<shop>** at €<price>
<bullet points explaining why>

---

*All prices include VAT (PVN). Delivery times and costs are estimates and may vary. Stock levels checked on <date>.*
```

### Chat Summary (CRITICAL — include product links)
When presenting the summary in the chat window, **always include direct product links** for the top recommendations. Use this format:

```
Here are the top options I found:

1. **<shop>** — €<price> — [Product Page](<url>)
   Rating: <rating>/5 (<count> reviews) | Stock: <status> | Delivery: <info>

2. **<shop>** — €<price> — [Product Page](<url>)
   Rating: <rating>/5 (<count> reviews) | Stock: <status> | Delivery: <info>

Full report saved to: <full path of the saved report>
```

## Tools to Use

- **playwright-cli** — Browse aggregator sites (salidzini.lv, kurpirkt.lv), navigate to product pages, verify stock and prices, check seller rating pages
- **SearXNG** — Initial product discovery, search across specific domains, find product URLs on individual store sites. Use a search tool if you have one; otherwise query it directly: `curl -s "http://127.0.0.1:8080/search?format=json&q=<url-encoded query>"` (on the host; inside the sandbox it is `http://searxng:8080`)
- **Web fetch** — Your web fetch tool if you have one, otherwise `curl -sL` with a realistic User-Agent, for quick page content when playwright is blocked
- **shell** — Process data, extract information from HTML, compile results

## Error Handling

- If a site blocks with Cloudflare (403), try structured data fallbacks first (APIs, JSON-LD, curl with UA), then fall back to aggregator price marked as "unconfirmed"
- Always document every Cloudflare-blocked site in the report — do not silently skip them
- If salidzini.lv seller page is unavailable, use the rating from the product listing itself
- If a product page shows "out of stock" or no purchase button, note it and exclude from recommendations
- If no sellers carry the product, report this clearly and suggest alternative search terms or similar products
- If the exact model isn't available, search for similar models and note the differences
- Never include aggregator prices in the final report unless the product page itself is inaccessible due to Cloudflare (in which case flag as "unconfirmed")

## Important Notes

1. **Always verify stock** — aggregator sites may show stale data. Always check the actual product page.
2. **Delivery** — prices are compared without delivery unless the user asked to include it (see Questions Before Searching). Always show each shop's delivery time and cost in the report, since some shops deliver free and others charge €2-5.
3. **Review count credibility** — sellers with 100+ reviews on salidzini.lv are generally more trustworthy. Sellers with < 50 reviews that are on neither of the user's lists are excluded (see Filtering Rules).
4. **Price fluctuations** — prices may change. The report should note the date it was generated.
5. **Foreign sellers** — Estonian sites (like smartech.ee) may ship to Latvia but factor in longer delivery times and potential customs considerations.
6. **Trusted list priority** — always include trusted list sellers in the report even if they're not the cheapest, as the user has established trust with them.
7. **Direct price verification required** — only include prices from product pages you have personally visited and verified. Aggregator prices are preliminary only.
8. **Cloudflare transparency** — always mention every site that was blocked by Cloudflare in the report. Never silently ignore inaccessible sites from your trusted list.
