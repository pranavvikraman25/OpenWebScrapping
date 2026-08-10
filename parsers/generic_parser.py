import bs4
import re
import json
from typing import List, Dict
from urllib.parse import urlparse, urljoin


class GenericParser:
    """Universal parser that extracts structured data from ANY website.
    
    Extraction strategy (in priority order):
    1. JSON-LD structured data (schema.org)
    2. HTML tables
    3. Repeating card/list patterns (articles, products, quotes, listings)
    4. Page metadata + headings + content blocks
    5. All content links (last resort)
    """

    def __init__(self, instruction: str):
        self.instruction = instruction.lower()

    async def parse(self, html: str, instruction: str) -> List[dict]:
        soup = bs4.BeautifulSoup(html, "html.parser")
        url = getattr(self, "url", "")
        records = []

        # ── Strategy 1: JSON-LD structured data ──
        jsonld_records = self._extract_jsonld(soup)
        if jsonld_records:
            records.extend(jsonld_records)

        # ── Strategy 2: HTML tables ──
        table_records = self._extract_tables(soup)
        if table_records:
            records.extend(table_records)

        # ── Strategy 3: Repeating card/list patterns ──
        card_records = self._extract_cards(soup, url)
        if card_records:
            records.extend(card_records)

        # ── Strategy 4: Page metadata + content blocks ──
        if not records:
            meta_records = self._extract_metadata_and_content(soup, url)
            records.extend(meta_records)

        # ── Strategy 5: All links on the page (always useful) ──
        if not records:
            link_records = self._extract_links(soup, url)
            if link_records:
                records.extend(link_records)

        return records

    # ─────────────────────────────────────────────
    # Strategy 1: JSON-LD
    # ─────────────────────────────────────────────
    def _extract_jsonld(self, soup: bs4.BeautifulSoup) -> List[dict]:
        records = []
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or "{}")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict) and item.get("@type"):
                        flat = self._flatten_jsonld(item)
                        if flat:
                            records.append(flat)
            except (json.JSONDecodeError, TypeError):
                continue
        return records

    def _flatten_jsonld(self, obj: dict, prefix: str = "") -> dict:
        flat = {}
        skip_keys = {"@context", "@id"}
        for k, v in obj.items():
            if k in skip_keys:
                continue
            key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
            if isinstance(v, dict):
                flat.update(self._flatten_jsonld(v, key))
            elif isinstance(v, list):
                if all(isinstance(i, str) for i in v):
                    flat[key] = ", ".join(v)
                elif all(isinstance(i, dict) for i in v):
                    flat[key] = "; ".join(
                        i.get("name", i.get("@type", str(i))) for i in v
                    )
                else:
                    flat[key] = str(v)
            else:
                flat[key] = str(v) if v is not None else ""
        return flat

    # ─────────────────────────────────────────────
    # Strategy 2: HTML tables
    # ─────────────────────────────────────────────
    def _extract_tables(self, soup: bs4.BeautifulSoup) -> List[dict]:
        records = []
        for table in soup.select("table"):
            rows = table.select("tr")
            if len(rows) < 2:
                continue

            headers = []
            thead = table.select_one("thead")
            if thead:
                headers = [th.get_text(strip=True) for th in thead.select("th, td")]
                data_rows = table.select("tbody tr") or rows[1:]
            else:
                first_row_cells = rows[0].select("th, td")
                if rows[0].select("th"):
                    headers = [th.get_text(strip=True) for th in first_row_cells]
                    data_rows = rows[1:]
                else:
                    headers = [f"Column_{i+1}" for i in range(len(first_row_cells))]
                    data_rows = rows

            if not headers:
                continue

            for row in data_rows:
                cells = [td.get_text(strip=True) for td in row.select("td, th")]
                if not any(cells):
                    continue
                record = {}
                for i, header in enumerate(headers):
                    record[header or f"Column_{i+1}"] = cells[i] if i < len(cells) else ""
                records.append(record)

        return records

    # ─────────────────────────────────────────────
    # Strategy 3: Repeating card/list patterns
    # ─────────────────────────────────────────────
    def _extract_cards(self, soup: bs4.BeautifulSoup, base_url: str) -> List[dict]:
        records = []

        # Expanded card selectors — covers most websites
        card_selectors = [
            "article",
            ".card", ".item", ".listing", ".post", ".entry",
            ".product", ".product_pod", ".result",
            ".quote", ".testimonial", ".review",
            "[class*='card']", "[class*='item']", "[class*='product']",
            ".news-item", ".event", ".block",
            "li.row", ".collection-item",
            ".col-xs-6.col-sm-4.col-md-3.col-lg-3",  # Bootstrap grid items
        ]

        best_cards = []
        best_selector = ""
        for selector in card_selectors:
            try:
                found = soup.select(selector)
            except Exception:
                continue
            # Use the selector that finds the most repeating elements (pattern)
            if len(found) >= 2 and len(found) > len(best_cards):
                best_cards = found
                best_selector = selector

        if not best_cards:
            return []

        for card in best_cards[:100]:  # Cap at 100
            record = self._extract_card_fields(card, base_url)
            if record:
                records.append(record)

        return records

    def _extract_card_fields(self, card, base_url: str) -> dict:
        """Extract all meaningful fields from a single card element."""
        record = {}

        # ── Title ──
        title_el = card.select_one("h1, h2, h3, h4, h5, h6")
        if title_el:
            record["Title"] = title_el.get_text(strip=True)
            # Check if title is inside a link
            title_link = title_el.select_one("a[href]") or title_el.find_parent("a")
            if title_link and title_link.get("href"):
                record["Link"] = urljoin(base_url, title_link["href"])

        # If no heading, try the first prominent link as title
        if "Title" not in record:
            first_link = card.select_one("a[href]")
            if first_link:
                link_text = first_link.get_text(strip=True)
                if link_text and len(link_text) > 2:
                    record["Title"] = link_text
                    record["Link"] = urljoin(base_url, first_link["href"])

        # ── Link (fallback) ──
        if "Link" not in record:
            link_el = card.select_one("a[href]")
            if link_el:
                record["Link"] = urljoin(base_url, link_el["href"])

        # ── Price ──
        # Try most specific selectors first to avoid grabbing parent containers
        price_el = (
            card.select_one(".price_color") or
            card.select_one(".price > *") or
            card.select_one(".price") or
            card.select_one("[class*='price']") or
            card.select_one(".cost, .amount")
        )
        if price_el:
            # Get only the direct text of the price element (not children like "Add to basket")
            price_text = price_el.string or price_el.get_text(strip=True)
            # Extract just the currency value using regex
            price_match = re.search(r'[\$\£\€\₹]?\s*[\d,]+\.?\d*', price_text or "")
            if price_match:
                record["Price"] = price_match.group(0).strip()
            elif price_text:
                record["Price"] = price_text.strip()[:30]

        # ── Rating / Stars ──
        rating_el = card.select_one(
            ".star-rating, [class*='rating'], [class*='stars'], "
            ".score, [class*='review']"
        )
        if rating_el:
            # Try to get rating from class name (e.g. "star-rating Three")
            classes = rating_el.get("class", [])
            rating_words = {"One": "1", "Two": "2", "Three": "3", "Four": "4", "Five": "5"}
            for cls in classes:
                if cls in rating_words:
                    record["Rating"] = f"{rating_words[cls]}/5"
                    break
            if "Rating" not in record:
                rating_text = rating_el.get_text(strip=True)
                if rating_text:
                    record["Rating"] = rating_text

        # ── Availability / Stock ──
        stock_el = card.select_one(
            ".availability, .instock, [class*='stock'], [class*='avail']"
        )
        if stock_el:
            record["Availability"] = stock_el.get_text(strip=True)

        # ── Description / Text content ──
        desc_el = card.select_one(
            "p, .description, .summary, .excerpt, .text, "
            ".content, blockquote, .quote-text, span.text"
        )
        if desc_el:
            desc_text = desc_el.get_text(strip=True)
            # Don't use the price text as description
            if desc_text and len(desc_text) > 5 and desc_text != record.get("Price", ""):
                record["Description"] = desc_text[:500]

        # ── Author ──
        author_el = card.select_one(
            ".author, [class*='author'], .by, .writer, "
            ".attribution, small.author, span.author"
        )
        if author_el:
            author_text = author_el.get_text(strip=True)
            # Clean up common prefixes
            for prefix in ["by ", "By ", "— ", "- ", "~ "]:
                if author_text.startswith(prefix):
                    author_text = author_text[len(prefix):]
            record["Author"] = author_text

        # ── Tags ──
        tags = []
        for tag_el in card.select(".tag, .category, .badge, .label, .chip, .tags a"):
            tag_text = tag_el.get_text(strip=True)
            if tag_text and tag_text not in tags:
                tags.append(tag_text)
        if tags:
            record["Tags"] = ", ".join(tags)

        # ── Image ──
        img_el = card.select_one("img[src]")
        if img_el:
            src = img_el.get("src", "") or img_el.get("data-src", "")
            if src:
                record["Image"] = urljoin(base_url, src)

        # ── Date ──
        date_el = card.select_one("time, .date, .time, [datetime], [class*='date']")
        if date_el:
            record["Date"] = date_el.get("datetime", date_el.get_text(strip=True))

        # Only keep cards that have at least a title or description
        if record.get("Title") or record.get("Description"):
            return record
        return None

    # ─────────────────────────────────────────────
    # Strategy 4: Page metadata + content
    # ─────────────────────────────────────────────
    def _extract_metadata_and_content(self, soup: bs4.BeautifulSoup, url: str) -> List[dict]:
        records = []

        meta = {"Source URL": url}

        title_el = soup.select_one("title")
        if title_el:
            meta["Page Title"] = title_el.get_text(strip=True)

        for tag in soup.select("meta[name], meta[property]"):
            name = tag.get("name", tag.get("property", "")).lower()
            content = tag.get("content", "")
            if not content:
                continue
            if "description" in name:
                meta["Description"] = content
            elif "keywords" in name:
                meta["Keywords"] = content
            elif "author" in name:
                meta["Author"] = content
            elif "og:title" in name:
                meta.setdefault("Page Title", content)
            elif "og:image" in name:
                meta["Image"] = content
            elif "og:site_name" in name:
                meta["Site Name"] = content

        records.append(meta)

        for heading in soup.select("h1, h2, h3"):
            heading_text = heading.get_text(strip=True)
            if not heading_text or len(heading_text) < 3:
                continue

            content_parts = []
            sibling = heading.find_next_sibling()
            while sibling and sibling.name not in ["h1", "h2", "h3"]:
                text = sibling.get_text(strip=True)
                if text and len(text) > 10:
                    content_parts.append(text[:300])
                if len(content_parts) >= 3:
                    break
                sibling = sibling.find_next_sibling()

            if content_parts:
                records.append({
                    "Section": heading_text,
                    "Content": " | ".join(content_parts),
                    "Source URL": url,
                })

        return records

    # ─────────────────────────────────────────────
    # Strategy 5: All links
    # ─────────────────────────────────────────────
    def _extract_links(self, soup: bs4.BeautifulSoup, base_url: str) -> List[dict]:
        records = []
        seen = set()

        main_content = soup.select_one("main, #content, .content, #main, article") or soup.body or soup

        for a in main_content.select("a[href]"):
            href = a.get("href", "").strip()
            text = a.get_text(strip=True)

            if not text or not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            if len(text) < 3:
                continue

            full_url = urljoin(base_url, href)
            if full_url in seen:
                continue
            seen.add(full_url)

            records.append({
                "Link Text": text[:200],
                "URL": full_url,
            })

        return records[:100]

    # ─────────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────────
    def get_page_title(self, html: str) -> str:
        soup = bs4.BeautifulSoup(html, "html.parser")
        title = soup.title.string if soup.title else "Scraped_Data"
        return re.sub(r'[^\w\s-]', '', title.strip()).replace(" ", "_")[:60]
