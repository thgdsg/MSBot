from __future__ import annotations

import asyncio
from typing import Any

import requests


class WebSearchError(RuntimeError):
    pass


class WebSearchService:
    """Busca web sem bloquear o event loop do Discord.

    Usa exclusivamente a API publica de respostas instantaneas do DuckDuckGo,
    sem exigir uma chave ou dependencia adicional.
    """

    DUCKDUCKGO_ENDPOINT = "https://api.duckduckgo.com/"
    MAX_QUERY_LENGTH = 600
    MAX_RESULTS = 5

    def __init__(self, timeout_seconds: int = 10):
        self.timeout_seconds = timeout_seconds

    async def search(self, query: str, max_results: int = 5) -> dict[str, Any]:
        query = str(query or "").strip()
        if not query:
            raise WebSearchError("a consulta de busca nao pode ser vazia.")
        if len(query) > self.MAX_QUERY_LENGTH:
            raise WebSearchError("a consulta de busca e muito longa.")
        try:
            max_results = int(max_results)
        except (TypeError, ValueError) as error:
            raise WebSearchError("max_results precisa ser um numero inteiro.") from error
        max_results = max(1, min(max_results, self.MAX_RESULTS))
        return await asyncio.to_thread(self._search_sync, query, max_results)

    def _search_sync(self, query: str, max_results: int) -> dict[str, Any]:
        return self._search_duckduckgo(query, max_results)

    def _search_duckduckgo(self, query: str, max_results: int) -> dict[str, Any]:
        response = requests.get(
            self.DUCKDUCKGO_ENDPOINT,
            params={
                "q": query,
                "format": "json",
                "no_html": "1",
                "no_redirect": "1",
                "skip_disambig": "1",
            },
            headers={"Accept": "application/json"},
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise WebSearchError(
                f"o provedor de busca retornou HTTP {response.status_code}."
            )
        try:
            body = response.json()
        except ValueError as error:
            raise WebSearchError("o provedor de busca retornou JSON invalido.") from error

        results: list[dict[str, str]] = []
        abstract = body.get("AbstractText")
        abstract_url = body.get("AbstractURL")
        if abstract and abstract_url:
            results.append(
                {
                    "title": str(body.get("Heading") or query)[:240],
                    "url": str(abstract_url)[:1000],
                    "snippet": str(abstract)[:800],
                }
            )

        def add_topics(topics: list[dict[str, Any]]) -> None:
            for topic in topics:
                if len(results) >= max_results:
                    return
                nested = topic.get("Topics")
                if isinstance(nested, list):
                    add_topics(nested)
                    continue
                url = str(topic.get("FirstURL") or "")
                text = str(topic.get("Text") or "")
                if url.startswith(("http://", "https://")) and text:
                    results.append(
                        {
                            "title": text.split(" - ", 1)[0][:240],
                            "url": url[:1000],
                            "snippet": text[:800],
                        }
                    )

        add_topics(body.get("RelatedTopics") or [])
        return {
            "provider": "duckduckgo_instant_answer",
            "query": query,
            "results": results[:max_results],
            "notice": "DuckDuckGo Instant Answer pode nao retornar resultados para todas as consultas",
        }
