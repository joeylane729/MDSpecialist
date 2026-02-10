"""
Google Scholar Search Endpoint

Testing-only endpoint for searching Google Scholar using the scholarly package.
"""

from fastapi import APIRouter, HTTPException, Query
import logging
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/google-scholar/search")
async def search_google_scholar(
    q: str = Query(..., min_length=1, description="Search keyword")
):
    """
    Search Google Scholar by keyword. Returns publication titles, authors, and links.
    Uses the scholarly Python package. No result limit; returns until the generator stops or errors.
    Testing mode only.
    """
    try:
        from scholarly import scholarly
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="scholarly package not installed. Run: pip install scholarly"
        )

    def _search():
        results = []
        search_query = scholarly.search_pubs(q)
        for pub in search_query:
            bib = pub.get("bib", {})
            author = bib.get("author", "")
            if isinstance(author, list):
                author = ", ".join(str(a) for a in author) if author else ""
            results.append({
                "title": bib.get("title", ""),
                "author": author,
                "year": bib.get("pub_year") or bib.get("year", ""),
                "venue": bib.get("venue", ""),
                "url": pub.get("pub_url", ""),
                "num_citations": pub.get("num_citations", 0),
            })
        return results

    try:
        results = await asyncio.to_thread(_search)
        return {"query": q, "results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Google Scholar search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=f"Google Scholar search failed: {str(e)}. Note: Heavy usage may trigger rate limiting."
        )
