"""
OpenThesaurus German thesaurus integration.

Public API — no authentication required.

Nodes:
  - openthesaurus.get_synonyms : Retrieve synonyms for a German word.
  - openthesaurus.search       : Full-text search across the thesaurus.

Base URL: https://www.openthesaurus.de/synonyme/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 — kept for consistency

log = structlog.get_logger(__name__)

_BASE_URL = "https://www.openthesaurus.de/synonyme/"


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"OpenThesaurus API error {r.status_code}: {detail}")


@register_node("openthesaurus.get_synonyms")
async def get_synonyms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Return synonym groups for a German word.

    Config / input keys:
      - word (str, required) : The German word to look up.
      - similar (bool)       : Include similar (fuzzy) matches. Default False.
      - substring (bool)     : Include substring matches. Default False.
    """
    word = config.get("word") or input_data.get("word")
    if not word:
        raise ValueError("openthesaurus.get_synonyms requires 'word'")

    similar = str(config.get("similar") or input_data.get("similar", False)).lower() == "true"
    substring = str(config.get("substring") or input_data.get("substring", False)).lower() == "true"

    params: dict = {"q": word, "format": "application/json"}
    if similar:
        params["similar"] = "true"
    if substring:
        params["substring"] = "true"

    log.info("openthesaurus.get_synonyms", word=word)
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=20.0) as client:
        r = await client.get("search", params=params)
        _raise_for_status(r)
        data = r.json()

    synsets = data.get("synsets", [])
    similar_terms = data.get("similarterms", [])
    substring_terms = data.get("substringterms", [])

    return {
        "word": word,
        "synsets": synsets,
        "similar_terms": similar_terms,
        "substring_terms": substring_terms,
        "total_synsets": len(synsets),
    }


@register_node("openthesaurus.search")
async def search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search the OpenThesaurus database.

    Config / input keys:
      - query (str, required) : Search query (German).
      - similar (bool)        : Include similar matches. Default True.
      - substring (bool)      : Include substring matches. Default True.
    """
    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("openthesaurus.search requires 'query'")

    similar = str(config.get("similar") or input_data.get("similar", True)).lower() != "false"
    substring = str(config.get("substring") or input_data.get("substring", True)).lower() != "false"

    params: dict = {"q": query, "format": "application/json"}
    if similar:
        params["similar"] = "true"
    if substring:
        params["substring"] = "true"

    log.info("openthesaurus.search", query=query)
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=20.0) as client:
        r = await client.get("search", params=params)
        _raise_for_status(r)
        data = r.json()

    synsets = data.get("synsets", [])
    # Flatten all terms from all synsets for easy consumption
    all_terms: list[str] = []
    for synset in synsets:
        for term in synset.get("terms", []):
            t = term.get("term")
            if t and t not in all_terms:
                all_terms.append(t)

    return {
        "query": query,
        "synsets": synsets,
        "all_terms": all_terms,
        "similar_terms": data.get("similarterms", []),
        "substring_terms": data.get("substringterms", []),
        "total_synsets": len(synsets),
    }
