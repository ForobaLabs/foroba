import httpx
import pytest
import respx

from searxng_client import search_web


@pytest.mark.asyncio
@respx.mock
async def test_search_web_returns_top_results():
    respx.get("http://localhost:8080/search").mock(
        return_value=httpx.Response(200, json={"results": [
            {"title": "ECB rates", "content": "The ECB kept rates unchanged.", "url": "https://ecb.europa.eu"},
            {"title": "Other", "content": "...", "url": "https://example.com"},
        ]})
    )
    results = await search_web("ECB interest rates", searxng_url="http://localhost:8080")
    assert len(results) == 2
    assert results[0]["title"] == "ECB rates"


@pytest.mark.asyncio
@respx.mock
async def test_search_web_returns_empty_on_failure():
    respx.get("http://localhost:8080/search").mock(return_value=httpx.Response(500))
    results = await search_web("anything", searxng_url="http://localhost:8080")
    assert results == []
