import re
from typing import List, Dict, Set
from collections import Counter


class SmartFilter:
    """Natural language instruction processor.
    
    Extracts keywords from plain English instructions like:
      "Extract only invention and technology-related information"
    
    Then scores each scraped record for relevance and filters out noise.
    """

    # Common stop words to ignore
    STOP_WORDS: Set[str] = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "it", "this", "that", "are", "was",
        "be", "has", "have", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "shall", "not", "no",
        "all", "each", "every", "both", "few", "more", "most", "other",
        "some", "such", "only", "just", "also", "than", "too", "very",
        "get", "find", "show", "give", "make", "take", "want", "need",
        "extract", "scrape", "collect", "gather", "pull", "fetch",
        "data", "information", "details", "content", "page", "site",
        "website", "web", "related", "about", "any", "me", "i", "my",
    }

    def __init__(self, instruction: str):
        self.instruction = instruction.lower().strip()
        self.keywords = self._extract_keywords(instruction)
        self.keyword_set = set(self.keywords)

    def _extract_keywords(self, instruction: str) -> List[str]:
        """Extract meaningful keywords from a natural language instruction."""
        # Clean and tokenize
        text = re.sub(r'[^\w\s]', ' ', instruction.lower())
        words = text.split()

        # Remove stop words
        keywords = [w for w in words if w not in self.STOP_WORDS and len(w) > 2]

        return keywords

    def filter(self, records: List[dict], threshold: float = 0.1) -> List[dict]:
        """Score and filter records by relevance to the instruction.
        
        If no keywords were extracted (empty/generic instruction), 
        returns all records unfiltered.
        """
        if not self.keywords or not records:
            return records

        scored = []
        for record in records:
            score = self._score_record(record)
            scored.append((score, record))

        # Sort by relevance (highest first)
        scored.sort(key=lambda x: x[0], reverse=True)

        # Filter out records below threshold
        filtered = [r for score, r in scored if score >= threshold]

        # If filtering removed everything, return top 50% instead
        if not filtered and scored:
            half = max(1, len(scored) // 2)
            filtered = [r for _, r in scored[:half]]

        return filtered

    def _score_record(self, record: dict) -> float:
        """Score a single record for relevance to keywords (0.0 to 1.0)."""
        # Combine all text from the record
        text_parts = []
        for key, value in record.items():
            text_parts.append(str(key).lower())
            text_parts.append(str(value).lower())
        full_text = " ".join(text_parts)

        if not full_text.strip():
            return 0.0

        # Count keyword matches
        matches = 0
        for keyword in self.keywords:
            if keyword in full_text:
                matches += 1

        if not self.keywords:
            return 1.0

        # Score = fraction of keywords matched
        score = matches / len(self.keywords)
        return score

    def get_keywords(self) -> List[str]:
        """Return extracted keywords (useful for frontend highlighting)."""
        return self.keywords
