"""Web and browser tools for Friday."""

from __future__ import annotations

import logging
import urllib.parse
import webbrowser
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _unwrap_ddg_url(raw_url: str) -> str:
    """Extract destination URL from DuckDuckGo redirect wrapper if present."""
    if not raw_url:
        return ""

    if "uddg=" in raw_url:
        try:
            parsed = urllib.parse.urlparse(raw_url)
            query_params = urllib.parse.parse_qs(parsed.query)
            if "uddg" in query_params and query_params["uddg"]:
                return str(query_params["uddg"][0])
        except Exception:
            pass

    if raw_url.startswith("//duckduckgo.com/l/?uddg="):
        try:
            parsed = urllib.parse.urlparse("https:" + raw_url)
            query_params = urllib.parse.parse_qs(parsed.query)
            if "uddg" in query_params and query_params["uddg"]:
                return str(query_params["uddg"][0])
        except Exception:
            pass

    if raw_url.startswith("//"):
        return f"https:{raw_url}"

    if raw_url.startswith("/") and not raw_url.startswith("//"):
        return f"https://duckduckgo.com{raw_url}"

    return raw_url


class WebSearchTool(BaseTool):
    """Tool to search the web using DuckDuckGo."""

    def __init__(self, timeout: int = 15) -> None:
        """Initialize WebSearchTool.

        Args:
            timeout: Network request timeout in seconds (default: 15).
        """
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web using DuckDuckGo. Returns top search results "
            "including titles, URLs, and text snippets."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up on the web.",
                },
                "max_results": {
                    "type": "integer",
                    "description": (
                        "Maximum number of search results to return (default: 5, max: 20)."
                    ),
                },
            },
            "required": ["query"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute web search.

        Args:
            query: The search term.
            max_results: Max number of results (default 5).

        Returns:
            ToolResult containing formatted search results.
        """
        query = kwargs.get("query")
        if not query or not str(query).strip():
            return ToolResult(success=False, error="Missing required parameter: query")

        query_str = str(query).strip()

        try:
            max_results = int(kwargs.get("max_results", 5))
        except (ValueError, TypeError):
            max_results = 5
        max_results = max(1, min(max_results, 20))

        try:
            results = self._fetch_search_results(query_str, max_results)

            if results is None:
                return ToolResult(
                    success=False,
                    error=f"Search request failed or was rate-limited for query: '{query_str}'",
                )

            if not results:
                return ToolResult(
                    success=True,
                    output=f"No search results found for: '{query_str}'",
                )

            output_lines = [f"Search results for '{query_str}':\n"]
            for idx, res in enumerate(results[:max_results], 1):
                output_lines.append(f"{idx}. {res['title']}")
                output_lines.append(f"   URL: {res['url']}")
                output_lines.append(f"   Snippet: {res['snippet']}\n")

            return ToolResult(success=True, output="\n".join(output_lines).strip())

        except requests.Timeout:
            return ToolResult(
                success=False,
                error=f"Web search timed out after {self.timeout} seconds.",
            )
        except requests.RequestException as exc:
            return ToolResult(
                success=False,
                error=f"Web search network error: {exc}",
            )
        except Exception as exc:
            logger.exception("Unexpected error in WebSearchTool")
            return ToolResult(
                success=False,
                error=f"Web search failed: {exc}",
            )

    def _fetch_search_results(
        self, query_str: str, max_results: int
    ) -> list[dict[str, str]] | None:
        """Fetch and parse DuckDuckGo search results across endpoints with fallbacks."""
        endpoints = [
            ("POST", "https://html.duckduckgo.com/html/", {"q": query_str}),
            ("GET", "https://html.duckduckgo.com/html/", {"q": query_str}),
            ("POST", "https://lite.duckduckgo.com/lite/", {"q": query_str}),
            ("GET", "https://lite.duckduckgo.com/lite/", {"q": query_str}),
        ]

        last_status: int | None = None
        bot_challenged = False

        for method, url, data in endpoints:
            try:
                if method == "POST":
                    response = requests.post(
                        url,
                        data=data,
                        headers=DEFAULT_HEADERS,
                        timeout=self.timeout,
                    )
                else:
                    response = requests.get(
                        url,
                        params=data,
                        headers=DEFAULT_HEADERS,
                        timeout=self.timeout,
                    )

                last_status = response.status_code

                # Check for rate-limiting or anti-bot challenge pages
                if response.status_code in (403, 429):
                    bot_challenged = True
                    logger.debug(
                        f"DDG endpoint {url} returned status {response.status_code}"
                    )
                    continue

                if response.status_code in (200, 202):
                    resp_text = response.text
                    # Check for anti-bot challenge signatures in HTML body
                    challenge_signatures = (
                        "anomaly-modal",
                        "challenge-form",
                        "duckduckgo.com/anomaly.html",
                        "bots are not allowed",
                        "automated traffic",
                    )
                    if any(sig in resp_text.lower() for sig in challenge_signatures):
                        bot_challenged = True
                        logger.debug(f"DDG endpoint {url} presented anti-bot challenge")
                        continue

                    results = self._parse_ddg_html(resp_text, max_results)
                    return results
            except requests.Timeout:
                raise
            except requests.RequestException as exc:
                logger.debug(f"DDG search endpoint {url} failed: {exc}")
                continue

        # Fallback to DDG Instant Answer API
        api_results = self._fetch_ddg_api(query_str, max_results)
        if api_results:
            return api_results

        if bot_challenged or (
            last_status is not None and last_status not in (200, 202)
        ):
            return None

        # Return empty list if endpoints responded with 200/202 but yielded 0 results
        return []

    def _fetch_ddg_api(
        self, query_str: str, max_results: int
    ) -> list[dict[str, str]] | None:
        """Fetch results from DuckDuckGo Instant Answer JSON API."""
        try:
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query_str,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
            }
            resp = requests.get(
                url, params=params, headers=DEFAULT_HEADERS, timeout=self.timeout
            )
            if resp.status_code not in (200, 202):
                return None
            data = resp.json()
            results: list[dict[str, str]] = []

            abstract = data.get("AbstractText", "")
            abstract_url = data.get("AbstractURL", "")
            heading = data.get("Heading", query_str)
            if abstract and abstract_url:
                results.append(
                    {
                        "title": heading or query_str,
                        "url": abstract_url,
                        "snippet": abstract,
                    }
                )

            def extract_topics(topic_list: list[Any]) -> None:
                for item in topic_list:
                    if len(results) >= max_results:
                        break
                    if isinstance(item, dict):
                        if "Topics" in item and isinstance(item["Topics"], list):
                            extract_topics(item["Topics"])
                        else:
                            text = str(item.get("Text", ""))
                            first_url = str(item.get("FirstURL", ""))
                            if text and first_url:
                                parts = text.split(" - ", 1)
                                title = parts[0] if len(parts) > 1 else text[:60]
                                snippet = parts[1] if len(parts) > 1 else text
                                results.append(
                                    {
                                        "title": title,
                                        "url": first_url,
                                        "snippet": snippet,
                                    }
                                )

            related = data.get("RelatedTopics", [])
            if isinstance(related, list):
                extract_topics(related)

            results_list = data.get("Results", [])
            if isinstance(results_list, list):
                extract_topics(results_list)

            return results if results else None
        except Exception as exc:
            logger.debug(f"DDG API query failed: {exc}")
            return None

    def _parse_ddg_html(self, html: str, max_results: int) -> list[dict[str, str]]:
        """Parse search results from DuckDuckGo HTML or Lite responses."""
        soup = BeautifulSoup(html, "html.parser")
        results: list[dict[str, str]] = []

        # 1. Standard HTML result format (.result / .result__body)
        result_elements = soup.select(".result")
        if not result_elements:
            result_elements = soup.select(".result__body")

        for el in result_elements:
            if len(results) >= max_results:
                break

            title_elem = el.select_one(".result__title a") or el.select_one(
                ".result__a"
            )
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            if not title:
                continue

            raw_url = str(title_elem.get("href", ""))
            actual_url = _unwrap_ddg_url(raw_url)

            snippet_elem = el.select_one(".result__snippet")
            snippet = (
                snippet_elem.get_text(strip=True)
                if snippet_elem
                else "No snippet available."
            )

            results.append(
                {
                    "title": title,
                    "url": actual_url,
                    "snippet": snippet,
                }
            )

        if results:
            return results

        # 2. Lite result format (table rows with a.result-link)
        lite_links = soup.select("a.result-link")
        for link in lite_links:
            if len(results) >= max_results:
                break

            title = link.get_text(strip=True)
            if not title:
                continue

            raw_url = str(link.get("href", ""))
            actual_url = _unwrap_ddg_url(raw_url)

            snippet = "No snippet available."
            row = link.find_parent("tr")
            if row:
                snippet_row = row.find_next_sibling("tr")
                if isinstance(snippet_row, Tag):
                    snippet_td = snippet_row.select_one("td.result-snippet")
                    if snippet_td:
                        snippet = snippet_td.get_text(strip=True)

            results.append(
                {
                    "title": title,
                    "url": actual_url,
                    "snippet": snippet,
                }
            )

        return results


class FetchWebPageTool(BaseTool):
    """Tool to fetch and parse readable text content from a web page."""

    def __init__(self, timeout: int = 15) -> None:
        """Initialize FetchWebPageTool.

        Args:
            timeout: Network request timeout in seconds (default: 15).
        """
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "fetch_web_page"

    @property
    def description(self) -> str:
        return (
            "Fetch and parse readable text content from a web URL without executing "
            "JavaScript. Extracts page title and clean text content."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": (
                        "The URL of the webpage to fetch (e.g. 'https://example.com', 'http://localhost:3000')."
                    ),
                },
                "max_length": {
                    "type": "integer",
                    "description": (
                        "Maximum character length of text content to return "
                        "(default: 8000)."
                    ),
                },
            },
            "required": ["url"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute fetching and parsing a webpage.

        Args:
            url: Webpage URL.
            max_length: Maximum content length in characters.

        Returns:
            ToolResult containing clean extracted text or error message.
        """
        url_input = kwargs.get("url")
        if not url_input or not str(url_input).strip():
            return ToolResult(success=False, error="Missing required parameter: url")

        url_raw = str(url_input).strip()
        if url_raw.startswith(("localhost", "127.0.0.1", "0.0.0.0", "[::1]")):
            url = f"http://{url_raw}"
        elif not url_raw.startswith(
            ("http://", "https://", "file://", "about:", "chrome:", "edge:")
        ):
            url = f"https://{url_raw}"
        else:
            url = url_raw

        try:
            max_length = int(kwargs.get("max_length", 8000))
        except (ValueError, TypeError):
            max_length = 8000
        max_length = max(100, max_length)

        try:
            response = requests.get(
                url,
                headers=DEFAULT_HEADERS,
                timeout=self.timeout,
                stream=True,
            )
            try:
                if response.status_code >= 400:
                    return ToolResult(
                        success=False,
                        error=f"HTTP Error {response.status_code}: {response.reason} for URL: {url}",
                    )

                # Check content type and prevent downloading huge binary payloads
                content_type = response.headers.get("Content-Type", "").lower()
                binary_types = (
                    "application/octet-stream",
                    "application/zip",
                    "application/x-zip-compressed",
                    "application/pdf",
                    "application/gzip",
                    "application/x-tar",
                    "application/x-7z-compressed",
                    "image/",
                    "video/",
                    "audio/",
                )
                if any(btype in content_type for btype in binary_types):
                    return ToolResult(
                        success=False,
                        error=(
                            f"Cannot parse binary content (Content-Type: '{content_type}') for URL: {url}. "
                            "FetchWebPageTool only supports HTML, text, and JSON documents."
                        ),
                    )

                # If text is directly provided (e.g. standard mocks or pre-decoded bodies)
                if hasattr(response, "text") and isinstance(response.text, str):
                    decoded_text = response.text
                else:
                    # Read bounded chunks from stream to prevent unbounded memory allocation
                    max_read_bytes = max(max_length * 4, 200_000)
                    content_chunks: list[bytes] = []
                    total_bytes = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if not chunk:
                            continue
                        content_chunks.append(chunk)
                        total_bytes += len(chunk)
                        if total_bytes >= max_read_bytes:
                            break

                    raw_bytes = b"".join(content_chunks)

                    # Auto-detect encoding for proper UTF-8 decoding
                    encoding = (
                        response.apparent_encoding or response.encoding or "utf-8"
                    )
                    try:
                        decoded_text = raw_bytes.decode(encoding, errors="replace")
                    except Exception:
                        decoded_text = raw_bytes.decode("utf-8", errors="replace")
                if "text/plain" in content_type:
                    text_content = decoded_text
                    title = url
                elif "application/json" in content_type:
                    text_content = decoded_text
                    title = f"JSON Data - {url}"
                else:
                    # Parse HTML with BeautifulSoup
                    soup = BeautifulSoup(decoded_text, "html.parser")

                    # Extract page title
                    title_elem = soup.title
                    title = (
                        title_elem.get_text(strip=True) if title_elem else "No Title"
                    )

                    # Remove non-content / boilerplate tags
                    for tag in soup(
                        [
                            "script",
                            "style",
                            "noscript",
                            "svg",
                            "header",
                            "footer",
                            "nav",
                            "aside",
                            "template",
                            "iframe",
                        ]
                    ):
                        tag.decompose()

                    # Get clean text
                    raw_text = soup.get_text(separator="\n")
                    lines = [
                        line.strip() for line in raw_text.splitlines() if line.strip()
                    ]
                    text_content = "\n".join(lines)
                    if not text_content:
                        text_content = "No readable text content found on this page."

                total_length = len(text_content)
                if total_length > max_length:
                    text_content = (
                        text_content[:max_length]
                        + f"\n\n... [Content truncated. Showing {max_length} of {total_length} characters]"
                    )

                output = f"Title: {title}\nURL: {url}\n\n{text_content}"
                return ToolResult(success=True, output=output)
            finally:
                response.close()

        except requests.Timeout:
            return ToolResult(
                success=False,
                error=f"Fetching web page timed out after {self.timeout} seconds.",
            )
        except requests.RequestException as exc:
            return ToolResult(
                success=False,
                error=f"Failed to fetch web page: {exc}",
            )
        except Exception as exc:
            logger.exception("Unexpected error in FetchWebPageTool")
            return ToolResult(
                success=False,
                error=f"Failed to parse web page: {exc}",
            )


class OpenBrowserTool(BaseTool):
    """Tool to open a URL in the user's default desktop web browser."""

    @property
    def name(self) -> str:
        return "open_browser"

    @property
    def description(self) -> str:
        return "Open a URL in the user's default desktop web browser (e.g. Chrome, Edge, Firefox)."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to open in the desktop web browser.",
                },
            },
            "required": ["url"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute opening a URL in the default browser.

        Args:
            url: The URL to open.

        Returns:
            ToolResult indicating success or error.
        """
        url_input = kwargs.get("url")
        if not url_input or not str(url_input).strip():
            return ToolResult(success=False, error="Missing required parameter: url")

        url_raw = str(url_input).strip()
        if url_raw.startswith(("localhost", "127.0.0.1", "0.0.0.0", "[::1]")):
            url = f"http://{url_raw}"
        elif not url_raw.startswith(
            ("http://", "https://", "file://", "about:", "chrome:", "edge:")
        ):
            url = f"https://{url_raw}"
        else:
            url = url_raw

        try:
            opened = webbrowser.open(url)
            if opened:
                return ToolResult(
                    success=True,
                    output=f"Successfully opened '{url}' in default browser.",
                )
            else:
                return ToolResult(
                    success=True,
                    output=f"Dispatched command to open '{url}' in default browser.",
                )
        except Exception as exc:
            logger.exception("Failed to open browser")
            return ToolResult(
                success=False,
                error=f"Failed to open URL in browser: {exc}",
            )
