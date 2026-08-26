try:
    from .BM25Query import BM25
except ImportError:
    BM25 = None

try:
    from .SemanticQuery import SemanticQuery
except ImportError:
    SemanticQuery = None

try:
    from .WebSearchFallback import WebSearchFallback, web_search_fallback
except ImportError:
    WebSearchFallback = None
    web_search_fallback = None

try:
    from .DirectQuery import get_all_chunks, get_all_chunks_with_fallback
except ImportError:
    get_all_chunks = None
    get_all_chunks_with_fallback = None

__all__ = [
    "BM25",
    "SemanticQuery",
    "WebSearchFallback",
    "web_search_fallback",
    "get_all_chunks",
    "get_all_chunks_with_fallback"
]
