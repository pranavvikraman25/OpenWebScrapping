# Parsers package

from urllib.parse import urlparse
from .umich_parser import UMichParser
from .accelerate_parser import AccelerateParser
from .ai_parser import AIParser
from .generic_parser import GenericParser

_parser_registry = []

def register_parser(domain_pattern, parser_cls):
    _parser_registry.append((domain_pattern, parser_cls))

# Register built‑in domain-specific parsers
register_parser("available-inventions.umich.edu", UMichParser)
register_parser("acceleratebluefund.com", AccelerateParser)

def get_parser(url: str, instruction: str):
    """Return an appropriate parser instance for *url*.
    
    Priority:
    1. Domain-specific parser (if registered)
    2. AI-assisted parser (if OpenAI key is configured)
    3. GenericParser (universal fallback — ALWAYS works)
    """
    hostname = urlparse(url).hostname or ""
    
    # 1. Check domain-specific parsers
    for pattern, cls in _parser_registry:
        if pattern in hostname:
            parser = cls(instruction)
            parser.url = url
            return parser
    
    # 2. Try AI-assisted parser if API key is available
    from utils.config import Settings
    settings = Settings()
    if settings.openai_api_key:
        parser = AIParser(instruction, settings.openai_api_key)
        parser.url = url
        return parser
    
    # 3. Universal fallback — works on ANY website
    parser = GenericParser(instruction)
    parser.url = url
    return parser
