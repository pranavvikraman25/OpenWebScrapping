# parsers/accelerate_parser.py
import bs4
from typing import List

class AccelerateParser:
    """Parse Accelerate Blue Fund portfolio pages.
    Heuristic looks for portfolio cards with class "portfolio-item" and extracts fields.
    """
    def __init__(self, instruction: str):
        self.instruction = instruction.lower()

    async def parse(self, html: str, instruction: str) -> List[dict]:
        soup = bs4.BeautifulSoup(html, "html.parser")
        records = []
        cards = soup.select(".portfolio-item, .portfolio-card, .project-card")
        for card in cards:
            data = {}
            # typical layout: <h3>Company Name</h3> followed by description and list items
            name_el = card.select_one("h3, .company-name, .title")
            if name_el:
                data["Company Name"] = name_el.get_text(strip=True)
            desc_el = card.select_one("p, .description, .company-description")
            if desc_el:
                data["Short Description"] = desc_el.get_text(strip=True)
            # Look for <span> or <li> elements that contain known labels
            label_map = {
                "industry": "Industry",
                "technology focus": "Technology Focus",
                "portfolio category": "Portfolio Category",
                "company website": "Company Website",
                "startup status": "Startup Status",
            }
            for label, field in label_map.items():
                el = card.find(string=lambda s: s and label in s.lower())
                if el:
                    # Assume the sibling contains the value
                    parent = el.parent
                    if parent and parent.next_sibling:
                        value = parent.next_sibling.get_text(strip=True) if hasattr(parent.next_sibling, 'get_text') else str(parent.next_sibling).strip()
                        data[field] = value
            # Ensure source URL placeholder – will be filled by backend later
            data["Source URL"] = ""
            if data:
                records.append(data)
        return records

    def get_page_title(self, html: str) -> str:
        soup = bs4.BeautifulSoup(html, "html.parser")
        title = soup.title.string if soup.title else "Accelerate_Portfolio"
        return title.strip().replace(" ", "_")
