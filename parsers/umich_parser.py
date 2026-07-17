// parsers/umich_parser.py
import bs4
from typing import List

class UMichParser:
    """Parse University of Michigan invention pages.
    This is a simple heuristic implementation that looks for
    <div class="field-label"> and corresponding <div class="field-item"> pairs.
    """
    def __init__(self, instruction: str):
        self.instruction = instruction.lower()

    async def parse(self, html: str, instruction: str) -> List[dict]:
        soup = bs4.BeautifulSoup(html, "html.parser")
        records = []
        # Find all product cards – the site uses <div class="view-content">
        cards = soup.select(".view-content .node-product")
        for card in cards:
            data = {}
            # Map known labels to fields
            label_map = {
                "technology name": "Technology Name",
                "technology number": "Technology Number",
                "description": "Short Description",
                "category": "Category",
                "inventor(s)": "Inventor(s)",
                "application": "Application",
                "industry": "Industry",
                "tags": "Tags",
            }
            # iterate over label/value pairs inside the card
            for label_el, value_el in zip(card.select(".field-label"), card.select(".field-item")):
                label = label_el.get_text(strip=True).lower()
                if label in label_map:
                    field = label_map[label]
                    data[field] = value_el.get_text(separator=" ", strip=True)
            if data:
                data["Source URL"] = ""
                records.append(data)
        return records

    def get_page_title(self, html: str) -> str:
        soup = bs4.BeautifulSoup(html, "html.parser")
        title = soup.title.string if soup.title else "UMich_Inventions"
        return title.strip().replace(" ", "_")
