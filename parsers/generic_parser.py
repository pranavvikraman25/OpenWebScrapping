import bs4
import re
import json
from typing import List, Dict
from urllib.parse import urlparse, urljoin


class GenericParser:
    """Universal parser that extracts structured data from ANY website.
    
    Extraction strategy:
    1. JSON-LD structured data (schema.org)
    2. HTML tables (filtered to ignore layout/calendar tables)
    3. Repeating card/list patterns (products, articles, repos, quotes, listings)
    4. Auto-detected repeating HTML containers (fallback for unstyled lists/grids)
    5. Page metadata + content blocks
    6. Main content links
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

        # ── Strategy 2: HTML tables (skip layout/heatmap tables) ──
        table_records = self._extract_tables(soup)
        if table_records:
            records.extend(table_records)

        # ── Strategy 3: Repeating card/list patterns ──
        card_records = self._extract_cards(soup, url)
        if card_records:
            records.extend(card_records)

        # ── Strategy 4: Fallback auto-detection for repeating containers ──
        if not records or len(records) < 2:
            auto_records = self._extract_auto_containers(soup, url)
            if auto_records:
                records.extend(auto_records)

        # ── Strategy 5: Page metadata + content blocks ──
        if not records:
            meta_records = self._extract_metadata_and_content(soup, url)
            records.extend(meta_records)

        # ── Strategy 6: All main content links ──
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
            classes = " ".join(table.get("class", []))
            if "ContributionCalendar" in classes or "js-calendar-table" in classes:
                continue

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

            valid_headers = [h for h in headers if h and len(h) > 1]
            if len(valid_headers) < 2:
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

        card_selectors = [
            # GitHub Specific
            "[itemprop='codeRepository']", ".pinned-item-list-item", ".repo",
            "li.col-12.mb-3", "ol.d-flex li", ".pinned-item-list-item-content",
            "div[class*='repo']", "li[class*='repo']",
            # Standard Web Items
            "article",
            ".card", ".item", ".listing", ".post", ".entry",
            ".product", ".product_pod", ".result",
            ".quote", ".testimonial", ".review",
            "[class*='card']", "[class*='item']", "[class*='product']",
            ".news-item", ".event", ".block",
            "li.row", ".collection-item",
            ".col-xs-6.col-sm-4.col-md-3.col-lg-3",
        ]

        best_cards = []
        for selector in card_selectors:
            try:
                found = soup.select(selector)
            except Exception:
                continue
            if len(found) >= 2 and len(found) > len(best_cards):
                best_cards = found

        if not best_cards:
            return []

        for card in best_cards[:100]:
            record = self._extract_card_fields(card, base_url)
            if record:
                records.append(record)

        return records

    def _extract_card_fields(self, card, base_url: str) -> dict:
        """Extract all meaningful fields from a single card element."""
        record = {}

        title_el = card.select_one("h1, h2, h3, h4, h5, h6, [itemprop='name']")
        if title_el:
            record["Title"] = title_el.get_text(strip=True)
            title_link = title_el.select_one("a[href]") or title_el.find_parent("a")
            if title_link and title_link.get("href"):
                record["Link"] = urljoin(base_url, title_link["href"])

        if "Title" not in record or not record["Title"]:
            repo_link = card.select_one("a[itemprop*='codeRepository'], a[href*='/']")
            if repo_link:
                link_text = repo_link.get_text(strip=True)
                if link_text and len(link_text) > 1:
                    record["Title"] = link_text
                    record["Link"] = urljoin(base_url, repo_link["href"])

        if "Title" not in record or not record["Title"]:
            first_link = card.select_one("a[href]")
            if first_link:
                link_text = first_link.get_text(strip=True)
                if link_text and len(link_text) > 2:
                    record["Title"] = link_text
                    record["Link"] = urljoin(base_url, first_link["href"])

        if not record.get("Title"):
            return None

        if "Link" not in record:
            link_el = card.select_one("a[href]")
            if link_el:
                record["Link"] = urljoin(base_url, link_el["href"])

        desc_el = card.select_one(
            "p, .description, .summary, .excerpt, .text, "
            ".content, blockquote, [itemprop='description'], "
            "span[class*='description'], div[class*='description']"
        )
        if desc_el:
            desc_text = desc_el.get_text(strip=True)
            if desc_text and len(desc_text) > 5:
                record["Description"] = desc_text[:500]

        lang_el = card.select_one("[itemprop='programmingLanguage'], .repo-language-color + span, [class*='language']")
        if lang_el:
            record["Language"] = lang_el.get_text(strip=True)

        tags = []
        for tag_el in card.select(".tag, .category, .badge, .label, .chip, .topic-tag"):
            tag_text = tag_el.get_text(strip=True)
            if tag_text and tag_text not in tags:
                tags.append(tag_text)
        if tags:
            record["Tags"] = ", ".join(tags)

        star_el = card.select_one("a[href*='/stargazers'], [class*='star']")
        if star_el:
            record["Stars"] = star_el.get_text(strip=True)

        fork_el = card.select_one("a[href*='/forks'], [class*='fork']")
        if fork_el:
            record["Forks"] = fork_el.get_text(strip=True)

        price_el = (
            card.select_one(".price_color") or
            card.select_one(".price > *") or
            card.select_one(".price") or
            card.select_one("[class*='price']") or
            card.select_one(".cost, .amount")
        )
        if price_el:
            price_text = price_el.string or price_el.get_text(strip=True)
            price_match = re.search(r'[\$\£\€\₹]?\s*[\d,]+\.?\d*', price_text or "")
            if price_match:
                record["Price"] = price_match.group(0).strip()
            elif price_text:
                record["Price"] = price_text.strip()[:30]

        rating_el = card.select_one(".star-rating, [class*='rating'], [class*='stars']")
        if rating_el:
            classes = rating_el.get("class", [])
            rating_words = {"One": "1", "Two": "2", "Three": "3", "Four": "4", "Five": "5"}
            for cls in classes:
                if cls in rating_words:
                    record["Rating"] = f"{rating_words[cls]}/5"
                    break

        img_el = card.select_one("img[src]")
        if img_el:
            src = img_el.get("src", "") or img_el.get("data-src", "")
            if src:
                record["Image"] = urljoin(base_url, src)

        return record

    def _extract_auto_containers(self, soup: bs4.BeautifulSoup, base_url: str) -> List[dict]:
        records = []
        for container in soup.select("ul, ol, main, div[class*='grid'], div[class*='list']"):
            children = container.find_all(["li", "div"], recursive=False)
            if len(children) >= 3:
                for child in children[:50]:
                    link = child.select_one("a[href]")
                    if not link:
                        continue
                    text = link.get_text(strip=True)
                    if not text or len(text) < 2:
                        continue
                    rec = {
                        "Title": text[:200],
                        "Link": urljoin(base_url, link["href"])
                    }
                    desc = child.select_one("p, span, div")
                    if desc and desc.get_text(strip=True) != text:
                        rec["Description"] = desc.get_text(strip=True)[:300]
                    records.append(rec)
                if len(records) >= 3:
                    break
        return records

    def _extract_metadata_and_content(self, soup: bs4.BeautifulSoup, url: str) -> List[dict]:
        records = []
        meta = {"Source URL": url}
        title_el = soup.select_one("title")
        if title_el:
            meta["Page Title"] = title_el.get_text(strip=True)

        for tag in soup.select("meta[name], meta[property]"):
            name = tag.get("name", tag.get("property", "")).lower()
            content = tag.get("content", "")
            if content and any(k in name for k in ["description", "keywords", "author", "og:title"]):
                meta[name] = content

        records.append(meta)
        return records

    def _extract_links(self, soup: bs4.BeautifulSoup, base_url: str) -> List[dict]:
        records = []
        seen = set()
        for a in soup.select("main a[href], body a[href]"):
            href = a.get("href", "").strip()
            text = a.get_text(strip=True)
            if text and len(text) > 2 and not href.startswith(("#", "javascript:")):
                full_url = urljoin(base_url, href)
                if full_url not in seen:
                    seen.add(full_url)
                    records.append({"Title": text[:200], "Link": full_url})
        return records[:100]

    def get_page_title(self, html: str) -> str:
        soup = bs4.BeautifulSoup(html, "html.parser")
        title = soup.title.string if soup.title else "Scraped_Data"
        return re.sub(r'[^\w\s-]', '', title.strip()).replace(" ", "_")[:60]
