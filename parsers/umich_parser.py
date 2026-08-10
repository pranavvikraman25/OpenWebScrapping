import bs4
import httpx
import asyncio
from typing import List
from urllib.parse import urljoin

class UMichParser:
    """Parse University of Michigan invention pages.
    Since the site has migrated to a new platform (e-lucid), product lists only
    contain titles, tags, and links. Detailed information (description, inventors, tech numbers)
    is fetched asynchronously from each individual product detail page.
    """
    def __init__(self, instruction: str):
        self.instruction = instruction.lower()

    async def parse(self, html: str, instruction: str) -> List[dict]:
        url = getattr(self, "url", "")
        # If this is a single product detail page, parse it directly
        if "/product/" in url and "/products" not in url:
            record = self.parse_detail_page(html, url)
            return [record] if record else []

        soup = bs4.BeautifulSoup(html, "html.parser")
        
        # 1. Find all product cards on the category/catalog page
        cards = soup.select(".card-product")
        if not cards:
            # Fallback to any links matching "/product/"
            cards = []
            for a in soup.select("a[href*='/product/']"):
                if a not in cards:
                    cards.append(a)
                    
        if not cards:
            return []
            
        base_url = "https://available-inventions.umich.edu"
        products = []
        for card in cards:
            link_el = card.select_one(".card-product__title-link") or card.select_one("a[href*='/product/']")
            if not link_el:
                continue
            title = link_el.get_text(strip=True)
            href = link_el.get("href", "")
            product_url = urljoin(base_url, href)
            
            if product_url not in [p["url"] for p in products]:
                products.append({
                    "title": title,
                    "url": product_url
                })
                
        # 2. Asynchronously fetch details for all products
        async def fetch_product_detail(client: httpx.AsyncClient, p: dict) -> dict:
            try:
                resp = await client.get(p["url"], timeout=15)
                if resp.status_code == 200:
                    return {"url": p["url"], "title": p["title"], "html": resp.text}
            except Exception:
                pass
            return {"url": p["url"], "title": p["title"], "html": None}

        async with httpx.AsyncClient(follow_redirects=True) as client:
            tasks = [fetch_product_detail(client, p) for p in products]
            results = await asyncio.gather(*tasks)

        # 3. Parse each product's detail page
        records = []
        for res in results:
            if not res["html"]:
                records.append({
                    "Technology Name": res["title"],
                    "Technology Number": "N/A",
                    "Short Description": "Failed to load details",
                    "Category": "Accessible Technologies",
                    "Inventor(s)": "N/A",
                    "Tags": "N/A",
                    "Source URL": res["url"]
                })
                continue
                
            record = self.parse_detail_page(res["html"], res["url"])
            if record:
                # Keep the title retrieved from the category page if detail page has no title
                if record["Technology Name"] == "UMich Invention":
                    record["Technology Name"] = res["title"]
                records.append(record)
            
        return records

    def parse_detail_page(self, html: str, url: str) -> dict:
        detail_soup = bs4.BeautifulSoup(html, "html.parser")
        
        # Title
        title_el = detail_soup.select_one(".product-description-box h1, h1")
        title = title_el.get_text(strip=True) if title_el else "UMich Invention"
        
        # Technology Number
        tech_num_el = (
            detail_soup.select_one(".product-id") 
            or detail_soup.find(lambda tag: tag.name in ["h6", "div", "span"] and "technology number" in tag.text.lower())
        )
        tech_number = "N/A"
        if tech_num_el:
            tech_text = tech_num_el.get_text(strip=True)
            if ":" in tech_text:
                tech_number = tech_text.split(":", 1)[1].strip()
            elif "No." in tech_text:
                tech_number = tech_text.split("No.", 1)[1].strip()
            else:
                tech_number = tech_text
                
        # Description
        desc_el = detail_soup.select_one(".description")
        description = ""
        if desc_el:
            description = desc_el.get_text(separator=" ", strip=True)
            
        # Inventors
        inventors = []
        for li in detail_soup.select("ul.collapsible-product li, .collapsible-product li, li"):
            header = li.select_one(".collapsible-header")
            if header and "inventor" in header.get_text(strip=True).lower():
                body = li.select_one(".collapsible-body")
                if body:
                    for div in body.select("div"):
                        name = div.get_text(strip=True)
                        if name and name not in inventors:
                            inventors.append(name)
                    if not inventors:
                        inventors = [body.get_text(strip=True)]
                        
        inventors_str = ", ".join(inventors) if inventors else "N/A"
        
        # Tags
        tags = []
        for tag_el in detail_soup.select(".chips-container .chip, .card-product__tags .chip, .chip"):
            tag_text = tag_el.get_text(strip=True)
            if tag_text and tag_text not in tags and "inventor" not in tag_text.lower():
                tags.append(tag_text)
        tags_str = ", ".join(tags) if tags else "N/A"
        
        return {
            "Technology Name": title,
            "Technology Number": tech_number,
            "Short Description": description,
            "Category": "Accessible Technologies",
            "Inventor(s)": inventors_str,
            "Tags": tags_str,
            "Source URL": url
        }

    def get_page_title(self, html: str) -> str:
        soup = bs4.BeautifulSoup(html, "html.parser")
        title = soup.title.string if soup.title else "UMich_Inventions"
        return title.strip().replace(" ", "_")
