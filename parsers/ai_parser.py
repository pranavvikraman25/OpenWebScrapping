# parsers/ai_parser.py
import os
import json
import httpx
from typing import List

class AIParser:
    """Fallback parser that uses an LLM (OpenAI) to extract data from raw HTML.
    It receives the full HTML and a natural‑language instruction and returns a list of
    dictionaries where each dict represents a row for the Excel file.
    """
    def __init__(self, instruction: str, api_key: str):
        self.instruction = instruction
        self.api_key = api_key
        self.endpoint = "https://api.openai.com/v1/chat/completions"

    async def parse(self, html: str, instruction: str) -> List[dict]:
        # Craft a prompt that asks the model to return JSON array of records.
        system_prompt = "You are a data extraction assistant. Given raw HTML of a webpage and a user instruction, return a JSON array where each element is a record containing only the fields mentioned in the instruction. Do not include any extra keys. If a field is missing for a record, set its value to null."
        user_prompt = f"HTML:\n```html\n{html}\n```\nInstruction: {instruction}\n\nRespond ONLY with the JSON array."
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0,
            "max_tokens": 2000
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.endpoint, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            # The response content is in choices[0].message.content
            content = data["choices"][0]["message"]["content"]
            try:
                records = json.loads(content)
            except json.JSONDecodeError:
                # Return empty list if parsing fails – backend will raise "No data" error.
                records = []
        return records

    def get_page_title(self, html: str) -> str:
        # Simple fallback – try to extract <title>
        start = html.find("<title>")
        end = html.find("</title>")
        if start != -1 and end != -1:
            title = html[start + 7:end]
            return title.strip().replace(" ", "_")
        return "scrape"
