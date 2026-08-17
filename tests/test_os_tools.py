"""Mock-based unit tests for native OS and web tools in Friday."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.core.tool_registry import ToolRegistry
from src.tools.system_tools import TimeTool, WeatherTool
from src.tools.web_tools import FetchWebPageTool, OpenBrowserTool, WebSearchTool
from src.tools.window_tool import WindowManagementTool

# ---------------------------------------------------------------------------
# Helper Mock Objects
# ---------------------------------------------------------------------------


class MockWindow:
    """Mock pygetwindow Win32Window object for headless testing."""

    def __init__(
        self,
        title: str = "Test Window",
        left: int = 100,
        top: int = 100,
        width: int = 800,
        height: int = 600,
        is_active: bool = False,
        is_maximized: bool = False,
        is_minimized: bool = False,
    ) -> None:
        self.title = title
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.isActive = is_active
        self.isMaximized = is_maximized
        self.isMinimized = is_minimized

        self.minimize_called = False
        self.maximize_called = False
        self.restore_called = False
        self.activate_called = False
        self.close_called = False
        self.moved_to: tuple[int, int] | None = None
        self.resized_to: tuple[int, int] | None = None

    def minimize(self) -> None:
        self.minimize_called = True
        self.is_minimized = True

    def maximize(self) -> None:
        self.maximize_called = True
        self.is_maximized = True

    def restore(self) -> None:
        self.restore_called = True
        self.is_maximized = False
        self.is_minimized = False

    def activate(self) -> None:
        self.activate_called = True
        self.isActive = True

    def close(self) -> None:
        self.close_called = True

    def moveTo(self, x: int, y: int) -> None:  # noqa: N802
        self.left = x
        self.top = y
        self.moved_to = (x, y)

    def resizeTo(self, width: int, height: int) -> None:  # noqa: N802
        self.width = width
        self.height = height
        self.resized_to = (width, height)


class MockScreenSize:
    """Mock pyautogui Size object."""

    def __init__(self, width: int = 1920, height: int = 1080) -> None:
        self.width = width
        self.height = height


# ---------------------------------------------------------------------------
# 1. Tool Schemas & Registry Tests
# ---------------------------------------------------------------------------


class TestToolSchemasAndRegistry:
    """Verify tool metadata and OpenAI function schemas."""

    def test_all_tools_schema_format(self) -> None:
        """Verify each OS tool adheres to the BaseTool schema specification."""
        tools = [
            WebSearchTool(),
            FetchWebPageTool(),
            OpenBrowserTool(),
            TimeTool(),
            WeatherTool(),
            WindowManagementTool(),
        ]

        for tool in tools:
            assert isinstance(tool.name, str) and len(tool.name) > 0
            assert isinstance(tool.description, str) and len(tool.description) > 0
            schema = tool.parameters_schema
            assert isinstance(schema, dict)
            assert schema.get("type") == "object"
            assert "properties" in schema

            openai_schema = tool.to_openai_schema()
            assert openai_schema["type"] == "function"
            assert openai_schema["function"]["name"] == tool.name
            assert openai_schema["function"]["description"] == tool.description
            assert openai_schema["function"]["parameters"] == schema

    def test_tool_registry_integration(self) -> None:
        """Verify all new tools register cleanly in ToolRegistry."""
        registry = ToolRegistry()
        web_search = WebSearchTool()
        fetch_page = FetchWebPageTool()
        open_browser = OpenBrowserTool()
        time_tool = TimeTool()
        weather_tool = WeatherTool()
        window_tool = WindowManagementTool()

        registry.register(web_search)
        registry.register(fetch_page)
        registry.register(open_browser)
        registry.register(time_tool)
        registry.register(weather_tool)
        registry.register(window_tool)

        assert len(registry) == 6
        assert "web_search" in registry
        assert "fetch_web_page" in registry
        assert "open_browser" in registry
        assert "get_current_time" in registry
        assert "get_weather" in registry
        assert "manage_window" in registry

        schemas = registry.get_tools_schema()
        assert len(schemas) == 6


# ---------------------------------------------------------------------------
# 2. WebSearchTool Tests
# ---------------------------------------------------------------------------


class TestWebSearchTool:
    """Unit tests for WebSearchTool with mocked HTTP requests."""

    SAMPLE_DDG_HTML = """
    <html>
      <body>
        <div class="result">
          <h2 class="result__title">
            <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.python.org%2F">
              Welcome to Python.org
            </a>
          </h2>
          <div class="result__snippet">
            The official home of the Python Programming Language.
          </div>
        </div>
        <div class="result">
          <h2 class="result__title">
            <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fdocs.python.org%2F3%2F">
              Python 3 Documentation
            </a>
          </h2>
          <div class="result__snippet">
            Comprehensive Python 3 official documentation and tutorials.
          </div>
        </div>
      </body>
    </html>
    """

    @patch("requests.post")
    def test_search_success(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = self.SAMPLE_DDG_HTML
        mock_post.return_value = mock_resp

        tool = WebSearchTool()
        res = tool.execute(query="python programming")

        assert res.success is True
        assert res.output is not None
        assert "Welcome to Python.org" in res.output
        assert "https://www.python.org/" in res.output
        assert "The official home of the Python" in res.output
        assert "Python 3 Documentation" in res.output

    @patch("requests.post")
    def test_search_max_results(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = self.SAMPLE_DDG_HTML
        mock_post.return_value = mock_resp

        tool = WebSearchTool()
        res = tool.execute(query="python", max_results=1)

        assert res.success is True
        assert res.output is not None
        assert "Welcome to Python.org" in res.output
        assert "Python 3 Documentation" not in res.output

    @patch("requests.post")
    def test_search_no_results(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body><div>No results found</div></body></html>"
        mock_post.return_value = mock_resp

        tool = WebSearchTool()
        res = tool.execute(query="randomxyz12345nonexistent")

        assert res.success is True
        assert res.output is not None
        assert "No search results found" in res.output

    def test_search_missing_query(self) -> None:
        tool = WebSearchTool()
        res = tool.execute()
        assert res.success is False
        assert "Missing required parameter" in (res.error or "")

        res_empty = tool.execute(query="   ")
        assert res_empty.success is False

    @patch("requests.post")
    @patch("requests.get")
    def test_search_ddg_lite_fallback(
        self, mock_get: MagicMock, mock_post: MagicMock
    ) -> None:
        """Verify fallback to DuckDuckGo Lite endpoint when standard HTML returns 500."""
        # Standard HTML POST and GET fail with 500
        html_fail = MagicMock()
        html_fail.status_code = 500

        # Lite endpoint returns 200 with table layout
        lite_success = MagicMock()
        lite_success.status_code = 200
        lite_success.text = """
        <html><body>
        <table>
          <tr>
            <td><a class="result-link" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.python.org%2F">Python Official</a></td>
          </tr>
          <tr>
            <td class="result-snippet">Python Programming Language Home.</td>
          </tr>
        </table>
        </body></html>
        """

        mock_post.side_effect = [html_fail, lite_success]
        mock_get.return_value = html_fail

        tool = WebSearchTool()
        res = tool.execute(query="python")

        assert res.success is True
        assert res.output is not None
        assert "Python Official" in res.output
        assert "https://www.python.org/" in res.output

    @patch("requests.post")
    @patch("requests.get")
    def test_search_ddg_instant_answer_api_fallback(
        self, mock_get: MagicMock, mock_post: MagicMock
    ) -> None:
        """Verify fallback to DuckDuckGo Instant Answer JSON API when HTML and Lite fail."""
        html_fail = MagicMock()
        html_fail.status_code = 429

        api_success = MagicMock()
        api_success.status_code = 200
        api_success.json.return_value = {
            "Heading": "Python Language",
            "AbstractText": "Python is a high-level general purpose programming language.",
            "AbstractURL": "https://www.python.org",
            "RelatedTopics": [
                {
                    "Text": "Python Documentation - Official docs for Python 3",
                    "FirstURL": "https://docs.python.org",
                },
                {
                    "Topics": [
                        {
                            "Text": "PyPI - Python Package Index repository",
                            "FirstURL": "https://pypi.org",
                        }
                    ]
                },
            ],
        }

        mock_post.return_value = html_fail
        mock_get.side_effect = [html_fail, html_fail, api_success]

        tool = WebSearchTool()
        res = tool.execute(query="python")

        assert res.success is True
        assert res.output is not None
        assert "Python Language" in res.output
        assert "https://www.python.org" in res.output
        assert "Python Documentation" in res.output
        assert "https://docs.python.org" in res.output
        assert "PyPI" in res.output
        assert "https://pypi.org" in res.output

    def test_unwrap_ddg_url_helper(self) -> None:
        """Verify _unwrap_ddg_url helper with various URL patterns."""
        from src.tools.web_tools import _unwrap_ddg_url

        assert (
            _unwrap_ddg_url(
                "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Ftest"
            )
            == "https://example.com/test"
        )
        assert (
            _unwrap_ddg_url("//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org")
            == "https://example.org"
        )
        assert _unwrap_ddg_url("//example.com/path") == "https://example.com/path"
        assert _unwrap_ddg_url("https://example.com") == "https://example.com"
        assert _unwrap_ddg_url("") == ""


# ---------------------------------------------------------------------------
# 3. FetchWebPageTool Tests
# ---------------------------------------------------------------------------


class TestFetchWebPageTool:
    """Unit tests for FetchWebPageTool with mocked HTTP responses."""

    SAMPLE_HTML = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Sample Web Page</title>
        <script>console.log("ignore me");</script>
        <style>body { color: red; }</style>
      </head>
      <body>
        <nav><a href="/home">Home</a></nav>
        <h1>Main Heading</h1>
        <p>This is the first paragraph with important text.</p>
        <p>This is the second paragraph with more details.</p>
        <footer>Copyright 2026</footer>
      </body>
    </html>
    """

    @patch("requests.get")
    def test_fetch_html_success(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.text = self.SAMPLE_HTML
        mock_get.return_value = mock_resp

        tool = FetchWebPageTool()
        res = tool.execute(url="https://example.com/article")

        assert res.success is True
        assert res.output is not None
        assert "Title: Sample Web Page" in res.output
        assert "Main Heading" in res.output
        assert "This is the first paragraph with important text." in res.output
        assert "console.log" not in res.output  # Script stripped
        assert "body { color: red; }" not in res.output  # Style stripped
        assert "Copyright 2026" not in res.output  # Footer stripped

    @patch("requests.get")
    def test_fetch_plain_text(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/plain"}
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.text = "Hello Plain World\nSecond line"
        mock_get.return_value = mock_resp

        tool = FetchWebPageTool()
        res = tool.execute(url="https://example.com/raw.txt")

        assert res.success is True
        assert "Hello Plain World" in (res.output or "")

    @patch("requests.get")
    def test_fetch_json(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.text = '{"status": "ok", "count": 42}'
        mock_get.return_value = mock_resp

        tool = FetchWebPageTool()
        res = tool.execute(url="https://api.example.com/data")

        assert res.success is True
        assert '"status": "ok"' in (res.output or "")

    @patch("requests.get")
    def test_fetch_truncation(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/plain"}
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.text = "A" * 5000
        mock_get.return_value = mock_resp

        tool = FetchWebPageTool()
        res = tool.execute(url="https://example.com/long", max_length=500)

        assert res.success is True
        assert res.output is not None
        assert "[Content truncated" in res.output

    @patch("requests.get")
    def test_fetch_auto_prepend_https(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/plain"}
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.text = "Content"
        mock_get.return_value = mock_resp

        tool = FetchWebPageTool()
        tool.execute(url="example.com/test")

        mock_get.assert_called_once()
        called_url = mock_get.call_args[0][0]
        assert called_url == "https://example.com/test"

    def test_fetch_missing_url(self) -> None:
        tool = FetchWebPageTool()
        res = tool.execute()
        assert res.success is False
        assert "Missing required parameter" in (res.error or "")

    @patch("requests.get")
    def test_fetch_http_404_error(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.reason = "Not Found"
        mock_get.return_value = mock_resp

        tool = FetchWebPageTool()
        res = tool.execute(url="https://example.com/notfound")

        assert res.success is False
        assert "404" in (res.error or "")

    @patch("requests.get")
    def test_fetch_timeout(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = requests.Timeout("Read timeout")

        tool = FetchWebPageTool()
        res = tool.execute(url="https://example.com/slow")

        assert res.success is False
        assert "timed out" in (res.error or "").lower()

    @patch("requests.get")
    def test_fetch_binary_content_rejected(self, mock_get: MagicMock) -> None:
        """Verify binary media types are rejected immediately without downloading."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/zip"}

        mock_get.return_value = mock_resp

        tool = FetchWebPageTool()
        res = tool.execute(url="https://example.com/archive.zip")

        assert res.success is False
        assert "Cannot parse binary content" in (res.error or "")

    @patch("requests.get")
    def test_fetch_localhost_auto_prepend_http(self, mock_get: MagicMock) -> None:
        """Verify localhost / 127.0.0.1 URLs prepend http:// rather than https://."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/plain"}
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.iter_content.return_value = [b"Local dev server OK"]

        mock_get.return_value = mock_resp

        tool = FetchWebPageTool()
        res = tool.execute(url="localhost:3000/api")

        assert res.success is True
        mock_get.assert_called_once()
        called_url = mock_get.call_args[0][0]
        assert called_url == "http://localhost:3000/api"

    @patch("requests.get")
    def test_fetch_empty_content_message(self, mock_get: MagicMock) -> None:
        """Verify empty HTML page returns a helpful fallback message."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.text = "<html><body></body></html>"

        mock_get.return_value = mock_resp

        tool = FetchWebPageTool()
        res = tool.execute(url="https://example.com/empty")

        assert res.success is True
        assert "No readable text content found" in (res.output or "")


# ---------------------------------------------------------------------------
# 4. OpenBrowserTool Tests
# ---------------------------------------------------------------------------


class TestOpenBrowserTool:
    """Unit tests for OpenBrowserTool with mocked webbrowser."""

    @patch("webbrowser.open")
    def test_open_browser_success(self, mock_open: MagicMock) -> None:
        mock_open.return_value = True

        tool = OpenBrowserTool()
        res = tool.execute(url="https://github.com")

        assert res.success is True
        assert "https://github.com" in (res.output or "")
        mock_open.assert_called_once_with("https://github.com")

    @patch("webbrowser.open")
    def test_open_browser_auto_prepend_https(self, mock_open: MagicMock) -> None:
        mock_open.return_value = True

        tool = OpenBrowserTool()
        tool.execute(url="github.com")

        mock_open.assert_called_once_with("https://github.com")

    @patch("webbrowser.open")
    def test_open_browser_localhost_prepends_http(self, mock_open: MagicMock) -> None:
        """Verify localhost URLs prepend http:// rather than opening as a Windows file path."""
        mock_open.return_value = True

        tool = OpenBrowserTool()
        tool.execute(url="localhost:8080/dashboard")

        mock_open.assert_called_once_with("http://localhost:8080/dashboard")

    def test_open_browser_missing_url(self) -> None:
        tool = OpenBrowserTool()
        res = tool.execute()
        assert res.success is False
        assert "Missing required parameter" in (res.error or "")

    @patch("webbrowser.open")
    def test_open_browser_exception(self, mock_open: MagicMock) -> None:
        mock_open.side_effect = Exception("OS Browser error")

        tool = OpenBrowserTool()
        res = tool.execute(url="https://example.com")

        assert res.success is False
        assert "OS Browser error" in (res.error or "")


# ---------------------------------------------------------------------------
# 5. TimeTool Tests
# ---------------------------------------------------------------------------


class TestTimeTool:
    """Unit tests for TimeTool."""

    def test_get_local_time(self) -> None:
        tool = TimeTool()
        res = tool.execute()

        assert res.success is True
        assert res.output is not None
        assert "Current Date and Time:" in res.output
        assert "Date:" in res.output
        assert "Time:" in res.output
        assert "Day of Week:" in res.output
        assert "Timezone:" in res.output
        assert "ISO 8601:" in res.output

    def test_get_utc_time(self) -> None:
        tool = TimeTool()
        res = tool.execute(timezone="UTC")

        assert res.success is True
        assert res.output is not None
        assert "UTC" in res.output

    def test_get_specific_timezone(self) -> None:
        tool = TimeTool()
        res = tool.execute(timezone="America/New_York")

        assert res.success is True
        assert res.output is not None
        assert "America/New_York" in res.output

    def test_get_timezone_aliases(self) -> None:
        tool = TimeTool()
        for tz_alias in ("EST", "PST", "BST", "JST", "CET"):
            res = tool.execute(timezone=tz_alias)
            assert res.success is True
            assert res.output is not None
            assert tz_alias in res.output

    def test_get_timezone_lowercase(self) -> None:
        """Verify case-insensitive timezone lookups."""
        tool = TimeTool()
        for tz_name in ("america/new_york", "europe/london", "asia/tokyo"):
            res = tool.execute(timezone=tz_name)
            assert res.success is True
            assert res.output is not None
            assert "Current Date and Time:" in res.output

    def test_get_timezone_city_names(self) -> None:
        """Verify city name timezone resolution."""
        tool = TimeTool()
        for city in ("Tokyo", "London", "Paris", "New York"):
            res = tool.execute(timezone=city)
            assert res.success is True
            assert res.output is not None
            assert "Current Date and Time:" in res.output

    def test_get_timezone_utc_offsets(self) -> None:
        """Verify explicit UTC/GMT offset strings."""
        tool = TimeTool()
        for offset_str in ("UTC+3", "GMT-5:30", "+04:00", "-0800"):
            res = tool.execute(timezone=offset_str)
            assert res.success is True
            assert res.output is not None
            assert "Current Date and Time:" in res.output

    def test_invalid_timezone(self) -> None:
        tool = TimeTool()
        res = tool.execute(timezone="NonExistent/Timezone_12345")

        assert res.success is False
        assert "Unknown timezone" in (res.error or "")


# ---------------------------------------------------------------------------
# 6. WeatherTool Tests
# ---------------------------------------------------------------------------


class TestWeatherTool:
    """Unit tests for WeatherTool with mocked wttr.in and Open-Meteo APIs."""

    MOCK_WTTR_JSON: dict[str, Any] = {
        "current_condition": [
            {
                "temp_C": "21",
                "temp_F": "70",
                "FeelsLikeC": "21",
                "FeelsLikeF": "70",
                "humidity": "45",
                "windspeedKmph": "12",
                "winddir16Point": "NW",
                "uvIndex": "5",
                "precipMM": "0.0",
                "weatherDesc": [{"value": "Sunny"}],
            }
        ],
        "nearest_area": [
            {
                "areaName": [{"value": "London"}],
                "country": [{"value": "United Kingdom"}],
            }
        ],
        "weather": [
            {
                "date": "2026-08-17",
                "maxtempC": "24",
                "mintempC": "15",
                "maxtempF": "75",
                "mintempF": "59",
                "astronomy": [{"sunrise": "05:48 AM", "sunset": "08:22 PM"}],
                "hourly": [{"weatherDesc": [{"value": "Sunny"}]}],
            }
        ],
    }

    @patch("requests.get")
    def test_weather_wttr_summary(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self.MOCK_WTTR_JSON
        mock_get.return_value = mock_resp

        tool = WeatherTool()
        res = tool.execute(location="London", format="summary")

        assert res.success is True
        assert res.output is not None
        assert "Weather for London, United Kingdom:" in res.output
        assert "Sunny" in res.output
        assert "21°C (70°F)" in res.output
        assert "Humidity: 45%" in res.output
        assert "12 km/h NW" in res.output

    @patch("requests.get")
    def test_weather_wttr_detailed(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self.MOCK_WTTR_JSON
        mock_get.return_value = mock_resp

        tool = WeatherTool()
        res = tool.execute(location="London", format="detailed")

        assert res.success is True
        assert res.output is not None
        assert "3-Day Forecast:" in res.output
        assert "2026-08-17: Sunny" in res.output
        assert "Sunrise: 05:48 AM" in res.output

    @patch("requests.get")
    def test_weather_fallback_open_meteo(self, mock_get: MagicMock) -> None:
        wttr_resp = MagicMock()
        wttr_resp.status_code = 500

        geo_resp = MagicMock()
        geo_resp.status_code = 200
        geo_resp.json.return_value = {
            "results": [
                {
                    "name": "Tokyo",
                    "country": "Japan",
                    "latitude": 35.6895,
                    "longitude": 139.6917,
                }
            ]
        }

        meteo_resp = MagicMock()
        meteo_resp.status_code = 200
        meteo_resp.json.return_value = {
            "current": {
                "temperature_2m": 28.5,
                "apparent_temperature": 30.2,
                "relative_humidity_2m": 65,
                "wind_speed_10m": 8.4,
                "precipitation": 0.0,
                "weather_code": 0,
            }
        }

        mock_get.side_effect = [wttr_resp, geo_resp, meteo_resp]

        tool = WeatherTool()
        res = tool.execute(location="Tokyo")

        assert res.success is True
        assert res.output is not None
        assert "Weather for Tokyo, Japan:" in res.output
        assert "Clear sky" in res.output
        assert "28.5°C" in res.output

    @patch("requests.get")
    def test_weather_direct_coordinates(self, mock_get: MagicMock) -> None:
        """Verify WeatherTool skips geocoding when provided direct coordinates."""
        wttr_resp = MagicMock()
        wttr_resp.status_code = 500

        meteo_resp = MagicMock()
        meteo_resp.status_code = 200
        meteo_resp.json.return_value = {
            "current": {
                "temperature_2m": 18.0,
                "apparent_temperature": 18.0,
                "relative_humidity_2m": 50,
                "wind_speed_10m": 10.0,
                "precipitation": 0.0,
                "weather_code": 1,
            }
        }

        mock_get.side_effect = [wttr_resp, meteo_resp]

        tool = WeatherTool()
        res = tool.execute(location="40.7128, -74.0060")

        assert res.success is True
        assert res.output is not None
        assert "Coordinates (40.7128, -74.006)" in res.output
        assert "Mainly clear" in res.output

    @patch("requests.get")
    def test_weather_non_ascii_city_fallback(self, mock_get: MagicMock) -> None:
        """Verify Open-Meteo geocoding fallback for non-ASCII city names."""
        wttr_resp = MagicMock()
        wttr_resp.status_code = 500

        # First English query returns empty results
        geo_resp_1 = MagicMock()
        geo_resp_1.status_code = 200
        geo_resp_1.json.return_value = {"results": []}

        # Second unconstrained/normalized query succeeds
        geo_resp_2 = MagicMock()
        geo_resp_2.status_code = 200
        geo_resp_2.json.return_value = {
            "results": [
                {
                    "name": "São Paulo",
                    "country": "Brazil",
                    "latitude": -23.55,
                    "longitude": -46.63,
                }
            ]
        }

        meteo_resp = MagicMock()
        meteo_resp.status_code = 200
        meteo_resp.json.return_value = {
            "current": {
                "temperature_2m": 25.0,
                "apparent_temperature": 25.0,
                "relative_humidity_2m": 60,
                "wind_speed_10m": 5.0,
                "precipitation": 0.0,
                "weather_code": 0,
            }
        }

        mock_get.side_effect = [wttr_resp, geo_resp_1, geo_resp_2, meteo_resp]

        tool = WeatherTool()
        res = tool.execute(location="São Paulo")

        assert res.success is True
        assert res.output is not None
        assert "Weather for São Paulo, Brazil:" in res.output

    @patch("requests.get")
    def test_weather_open_meteo_detailed_fahrenheit(self, mock_get: MagicMock) -> None:
        """Verify Open-Meteo detailed forecast outputs high and low in °C and °F."""
        wttr_resp = MagicMock()
        wttr_resp.status_code = 500

        geo_resp = MagicMock()
        geo_resp.status_code = 200
        geo_resp.json.return_value = {
            "results": [
                {
                    "name": "London",
                    "country": "United Kingdom",
                    "latitude": 51.5074,
                    "longitude": -0.1278,
                }
            ]
        }

        meteo_resp = MagicMock()
        meteo_resp.status_code = 200
        meteo_resp.json.return_value = {
            "current": {
                "temperature_2m": 20.0,
                "apparent_temperature": 20.0,
                "relative_humidity_2m": 50,
                "wind_speed_10m": 10.0,
                "precipitation": 0.0,
                "weather_code": 0,
            },
            "daily": {
                "time": ["2026-08-17"],
                "temperature_2m_max": [25.0],
                "temperature_2m_min": [15.0],
                "weather_code": [0],
                "sunrise": ["2026-08-17T05:48"],
                "sunset": ["2026-08-17T20:22"],
            },
        }

        mock_get.side_effect = [wttr_resp, geo_resp, meteo_resp]

        tool = WeatherTool()
        res = tool.execute(location="London", format="detailed")

        assert res.success is True
        assert res.output is not None
        assert "25.0°C (77.0°F)" in res.output
        assert "15.0°C (59.0°F)" in res.output

    def test_weather_missing_location(self) -> None:
        tool = WeatherTool()
        res = tool.execute()
        assert res.success is False
        assert "Missing required parameter" in (res.error or "")

    @patch("requests.get")
    def test_weather_all_services_fail(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = requests.ConnectionError("Offline")

        tool = WeatherTool()
        res = tool.execute(location="Paris")

        assert res.success is False
        assert "Could not retrieve weather data" in (res.error or "")


# ---------------------------------------------------------------------------
# 7. WindowManagementTool Tests
# ---------------------------------------------------------------------------


class TestWindowManagementTool:
    """Unit tests for WindowManagementTool with mocked OS window managers."""

    @patch("pygetwindow.getAllWindows")
    def test_list_windows(self, mock_get_all: MagicMock) -> None:
        w1 = MockWindow(
            title="Visual Studio Code - Friday",
            left=0,
            top=0,
            width=1920,
            height=1080,
            is_active=True,
        )
        w2 = MockWindow(
            title="Google Chrome",
            left=100,
            top=100,
            width=1200,
            height=800,
        )
        w_blank = MockWindow(title="")  # Should be filtered out

        mock_get_all.return_value = [w1, w2, w_blank]

        tool = WindowManagementTool()
        res = tool.execute(action="list")

        assert res.success is True
        assert res.output is not None
        assert "Open Windows (total: 2):" in res.output
        assert '1. "Visual Studio Code - Friday" [Active]' in res.output
        assert '2. "Google Chrome"' in res.output

    @patch("pygetwindow.getAllWindows")
    def test_list_empty_windows(self, mock_get_all: MagicMock) -> None:
        mock_get_all.return_value = []

        tool = WindowManagementTool()
        res = tool.execute(action="list")

        assert res.success is True
        assert "No active desktop windows found" in (res.output or "")

    @patch("pygetwindow.getAllWindows")
    def test_minimize_window(self, mock_get_all: MagicMock) -> None:
        target = MockWindow(title="Spotify Free")
        mock_get_all.return_value = [target]

        tool = WindowManagementTool()
        res = tool.execute(action="minimize", title="spotify")

        assert res.success is True
        assert target.minimize_called is True
        assert "Successfully minimized window 'Spotify Free'" in (res.output or "")

    @patch("pygetwindow.getAllWindows")
    def test_maximize_window(self, mock_get_all: MagicMock) -> None:
        target = MockWindow(title="Notepad")
        mock_get_all.return_value = [target]

        tool = WindowManagementTool()
        res = tool.execute(action="maximize", title="notepad")

        assert res.success is True
        assert target.maximize_called is True
        assert "Successfully maximized window 'Notepad'" in (res.output or "")

    @patch("pygetwindow.getAllWindows")
    def test_restore_window(self, mock_get_all: MagicMock) -> None:
        target = MockWindow(title="Calculator", is_minimized=True)
        mock_get_all.return_value = [target]

        tool = WindowManagementTool()
        res = tool.execute(action="restore", title="Calculator")

        assert res.success is True
        assert target.restore_called is True
        assert "Successfully restored window 'Calculator'" in (res.output or "")

    @patch("pygetwindow.getAllWindows")
    def test_activate_window(self, mock_get_all: MagicMock) -> None:
        target = MockWindow(title="Terminal", is_minimized=True)
        mock_get_all.return_value = [target]

        tool = WindowManagementTool()
        res = tool.execute(action="activate", title="terminal")

        assert res.success is True
        assert target.activate_called is True
        assert target.restore_called is True  # Restored since it was minimized
        assert "Successfully activated window 'Terminal'" in (res.output or "")

    @patch("pygetwindow.getAllWindows")
    def test_close_window(self, mock_get_all: MagicMock) -> None:
        target = MockWindow(title="Unsaved Doc - WordPad")
        mock_get_all.return_value = [target]

        tool = WindowManagementTool()
        res = tool.execute(action="close", title="WordPad")

        assert res.success is True
        assert target.close_called is True
        assert "Successfully closed window" in (res.output or "")

    @patch("pygetwindow.getAllWindows")
    def test_find_window_by_tokens(self, mock_get_all: MagicMock) -> None:
        """Verify finding window by token matching."""
        target = MockWindow(title="index.ts - my-project - Visual Studio Code")
        mock_get_all.return_value = [target]

        tool = WindowManagementTool()
        res = tool.execute(action="minimize", title="Visual Studio Code")

        assert res.success is True
        assert target.minimize_called is True

    @pytest.mark.parametrize(
        ("snap_pos", "expected_box"),
        [
            ("left", (0, 0, 960, 1080)),
            ("right", (960, 0, 960, 1080)),
            ("top", (0, 0, 1920, 540)),
            ("bottom", (0, 540, 1920, 540)),
            ("top-left", (0, 0, 960, 540)),
            ("top-right", (960, 0, 960, 540)),
            ("bottom-left", (0, 540, 960, 540)),
            ("bottom-right", (960, 540, 960, 540)),
            ("center", (480, 270, 960, 540)),
        ],
    )
    @patch("src.tools.window_tool._get_monitor_work_area")
    @patch("pygetwindow.getAllWindows")
    def test_snap_positions(
        self,
        mock_get_all: MagicMock,
        mock_get_work_area: MagicMock,
        snap_pos: str,
        expected_box: tuple[int, int, int, int],
    ) -> None:
        mock_get_work_area.return_value = (0, 0, 1920, 1080)
        target = MockWindow(title="Editor", is_maximized=True)
        mock_get_all.return_value = [target]

        tool = WindowManagementTool()
        res = tool.execute(action="snap", title="Editor", snap_position=snap_pos)

        assert res.success is True
        assert target.restore_called is True  # Maximized window was restored
        assert target.moved_to == (expected_box[0], expected_box[1])
        assert target.resized_to == (expected_box[2], expected_box[3])
        assert f"Successfully snapped window 'Editor' to '{snap_pos}'" in (
            res.output or ""
        )

    @patch("src.tools.window_tool._get_monitor_work_area")
    @patch("pygetwindow.getAllWindows")
    def test_snap_secondary_monitor(
        self,
        mock_get_all: MagicMock,
        mock_get_work_area: MagicMock,
    ) -> None:
        """Verify snapping properly applies secondary monitor offset coordinates."""
        mock_get_work_area.return_value = (1920, 0, 1920, 1080)
        target = MockWindow(title="Editor Monitor 2", left=2000, top=100)
        mock_get_all.return_value = [target]

        tool = WindowManagementTool()
        res = tool.execute(
            action="snap", title="Editor Monitor 2", snap_position="left"
        )

        assert res.success is True
        assert target.moved_to == (1920, 0)
        assert target.resized_to == (960, 1080)

    @patch("pygetwindow.getAllWindows")
    def test_snap_maximize(self, mock_get_all: MagicMock) -> None:
        target = MockWindow(title="Editor")
        mock_get_all.return_value = [target]

        tool = WindowManagementTool()
        res = tool.execute(action="snap", title="Editor", snap_position="maximize")

        assert res.success is True
        assert target.maximize_called is True

    @patch("pygetwindow.getAllWindows")
    def test_move_resize_custom(self, mock_get_all: MagicMock) -> None:
        target = MockWindow(title="Custom App")
        mock_get_all.return_value = [target]

        tool = WindowManagementTool()
        res = tool.execute(
            action="move_resize",
            title="Custom App",
            x=200,
            y=150,
            width=800,
            height=600,
        )

        assert res.success is True
        assert target.moved_to == (200, 150)
        assert target.resized_to == (800, 600)

    @patch("pygetwindow.getAllWindows")
    def test_move_resize_partial_coords(self, mock_get_all: MagicMock) -> None:
        """Verify partial coordinates (e.g. x-only, width-only) update correctly without error."""
        target = MockWindow(
            title="Partial App", left=100, top=150, width=500, height=400
        )
        mock_get_all.return_value = [target]

        tool = WindowManagementTool()
        # Move x only
        res1 = tool.execute(action="move_resize", title="Partial App", x=300)
        assert res1.success is True
        assert target.moved_to == (300, 150)

        # Resize width only
        res2 = tool.execute(action="move_resize", title="Partial App", width=700)
        assert res2.success is True
        assert target.resized_to == (700, 400)

    def test_move_resize_no_params_error(self) -> None:
        tool = WindowManagementTool()
        target = MockWindow(title="App")
        with patch("pygetwindow.getAllWindows", return_value=[target]):
            res = tool.execute(action="move_resize", title="App")
            assert res.success is False
            assert "at least one of (x, y, width, height)" in (res.error or "")

    @patch("pygetwindow.getAllWindows")
    def test_window_not_found(self, mock_get_all: MagicMock) -> None:
        mock_get_all.return_value = [MockWindow(title="Explorer")]

        tool = WindowManagementTool()
        res = tool.execute(action="minimize", title="Photoshop")

        assert res.success is False
        assert "No open window found matching title: 'Photoshop'" in (res.error or "")

    def test_window_missing_action(self) -> None:
        tool = WindowManagementTool()
        res = tool.execute()
        assert res.success is False
        assert "Missing required parameter: action" in (res.error or "")

    def test_window_invalid_action(self) -> None:
        tool = WindowManagementTool()
        res = tool.execute(action="destroy_everything")
        assert res.success is False
        assert "Invalid action" in (res.error or "")

    def test_window_missing_title_for_action(self) -> None:
        tool = WindowManagementTool()
        res = tool.execute(action="maximize")
        assert res.success is False
        assert "Missing required parameter 'title'" in (res.error or "")

    def test_get_monitor_work_area_fallback(self) -> None:
        """Verify _get_monitor_work_area falls back to pyautogui.size when Win32 fails."""
        from src.tools.window_tool import _get_monitor_work_area

        mock_window = MockWindow(left=100, top=100, width=800, height=600)
        mock_pyautogui = MagicMock()
        mock_pyautogui.size.return_value = MockScreenSize(2560, 1440)

        with patch(
            "ctypes.windll.user32.MonitorFromPoint", side_effect=Exception("No Win32")
        ):
            work_area = _get_monitor_work_area(mock_window, mock_pyautogui)
            assert work_area == (0, 0, 2560, 1440)

    @patch("pygetwindow.getAllWindows", side_effect=Exception("Desktop access denied"))
    def test_list_windows_exception(self, mock_get_all: MagicMock) -> None:
        """Verify _list_windows handles system/permission exceptions gracefully."""
        tool = WindowManagementTool()
        res = tool.execute(action="list")
        assert res.success is False
        assert "Failed to retrieve desktop windows" in (res.error or "")

    @patch("src.tools.window_tool._get_monitor_work_area")
    @patch("pygetwindow.getAllWindows")
    def test_snap_window_with_underscores(
        self,
        mock_get_all: MagicMock,
        mock_get_work_area: MagicMock,
    ) -> None:
        """Verify snap_position with underscores (e.g. top_left) is normalized and succeeds."""
        mock_get_work_area.return_value = (0, 0, 1920, 1080)
        target = MockWindow(title="VS Code")
        mock_get_all.return_value = [target]

        tool = WindowManagementTool()
        res = tool.execute(action="snap", title="VS Code", snap_position="top_left")

        assert res.success is True
        assert target.moved_to == (0, 0)
        assert target.resized_to == (960, 540)
        assert "top-left" in (res.output or "")

    @patch("pygetwindow.getAllWindows")
    def test_move_resize_negative_dimensions_error(
        self, mock_get_all: MagicMock
    ) -> None:
        """Verify non-positive width/height parameters are rejected."""
        target = MockWindow(title="App")
        mock_get_all.return_value = [target]

        tool = WindowManagementTool()
        res_w = tool.execute(action="move_resize", title="App", width=-100)
        assert res_w.success is False
        assert "must be a positive integer" in (res_w.error or "")

        res_h = tool.execute(action="move_resize", title="App", height=0)
        assert res_h.success is False
        assert "must be a positive integer" in (res_h.error or "")

    def test_get_monitor_work_area_with_hwnd(self) -> None:
        """Verify _get_monitor_work_area utilizes MonitorFromWindow when HWND is present."""
        from src.tools.window_tool import _get_monitor_work_area

        mock_window = MockWindow(left=-32000, top=-32000, width=800, height=600)
        mock_window._hWnd = 12345  # type: ignore[attr-defined]
        mock_pyautogui = MagicMock()

        # Should execute safely and return work area tuple
        work_area = _get_monitor_work_area(mock_window, mock_pyautogui)
        assert isinstance(work_area, tuple)
        assert len(work_area) == 4

    def test_ensure_dpi_aware(self) -> None:
        """Verify _ensure_dpi_aware executes without unhandled exception."""
        from src.tools.window_tool import _ensure_dpi_aware

        _ensure_dpi_aware()

    def test_get_monitor_work_area_tuple_size(self) -> None:
        """Verify _get_monitor_work_area handles plain tuple returned by pyautogui.size()."""
        from src.tools.window_tool import _get_monitor_work_area

        mock_window = MockWindow(left=100, top=100, width=800, height=600)
        mock_pyautogui = MagicMock()
        mock_pyautogui.size.return_value = (3840, 2160)

        with patch(
            "ctypes.windll.user32.MonitorFromPoint", side_effect=Exception("No Win32")
        ):
            work_area = _get_monitor_work_area(mock_window, mock_pyautogui)
            assert work_area == (0, 0, 3840, 2160)

    @patch(
        "pygetwindow.getAllWindows",
        side_effect=NotImplementedError("PyGetWindow currently only supports Windows"),
    )
    def test_window_action_linux_not_implemented_error(
        self, mock_get_all: MagicMock
    ) -> None:
        """Verify Linux/headless CI platform exception is propagated cleanly as ToolResult error."""
        tool = WindowManagementTool()
        res = tool.execute(action="minimize", title="Chrome")
        assert res.success is False
        assert "Window management action 'minimize' failed" in (res.error or "")
        assert "PyGetWindow currently only supports Windows" in (res.error or "")

    @patch("pygetwindow.getAllWindows")
    def test_move_resize_non_integer_error(self, mock_get_all: MagicMock) -> None:
        """Verify invalid non-integer coordinates are rejected with descriptive messages."""
        target = MockWindow(title="App")
        mock_get_all.return_value = [target]

        tool = WindowManagementTool()
        res_x = tool.execute(action="move_resize", title="App", x="invalid_x")
        assert res_x.success is False
        assert "Window x coordinate must be an integer" in (res_x.error or "")

        res_w = tool.execute(action="move_resize", title="App", width="invalid_w")
        assert res_w.success is False
        assert "Window width must be an integer" in (res_w.error or "")


# ---------------------------------------------------------------------------
# 8. Adversarial & Edge Case Tests for Web & System Tools
# ---------------------------------------------------------------------------


class TestAdversarialEdgeCases:
    """Adversarial stress and edge-case test suite."""

    @patch("requests.post")
    @patch("requests.get")
    def test_web_search_anti_bot_challenge_detection(
        self, mock_get: MagicMock, mock_post: MagicMock
    ) -> None:
        """Verify DuckDuckGo anti-bot challenge HTML body is recognized as rate-limiting."""
        challenge_resp = MagicMock()
        challenge_resp.status_code = 200
        challenge_resp.text = "<html><body><div id='anomaly-modal'>Bots are not allowed</div></body></html>"

        api_fail = MagicMock()
        api_fail.status_code = 429

        mock_post.return_value = challenge_resp
        mock_get.side_effect = [challenge_resp, challenge_resp, api_fail]

        tool = WebSearchTool()
        res = tool.execute(query="stress test query")

        assert res.success is False
        assert "rate-limited" in (res.error or "").lower()

    @patch("requests.get")
    def test_fetch_web_page_tar_and_7z_rejected(self, mock_get: MagicMock) -> None:
        """Verify tar and 7z archive content types are rejected without downloading."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/x-tar"}

        mock_get.return_value = mock_resp

        tool = FetchWebPageTool()
        res = tool.execute(url="https://example.com/data.tar")

        assert res.success is False
        assert "Cannot parse binary content" in (res.error or "")

    @patch("requests.get")
    def test_fetch_web_page_local_hostnames(self, mock_get: MagicMock) -> None:
        """Verify 0.0.0.0 and [::1] local URLs prepend http://."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/plain"}
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.iter_content.return_value = [b"Local API"]
        mock_get.return_value = mock_resp

        tool = FetchWebPageTool()
        tool.execute(url="0.0.0.0:5000/status")

        called_url = mock_get.call_args[0][0]
        assert called_url == "http://0.0.0.0:5000/status"

    @patch("webbrowser.open")
    def test_open_browser_custom_schemes(self, mock_open: MagicMock) -> None:
        """Verify chrome://, about:, edge:// URLs are passed without prepending https://."""
        mock_open.return_value = True

        tool = OpenBrowserTool()
        tool.execute(url="about:blank")
        mock_open.assert_called_with("about:blank")

        tool.execute(url="chrome://settings")
        mock_open.assert_called_with("chrome://settings")

    def test_time_tool_out_of_bounds_offsets(self) -> None:
        """Verify out-of-range UTC/GMT offsets do not raise unhandled ValueError."""
        tool = TimeTool()
        for bad_offset in ("UTC+25", "GMT-99", "+99:99", "-5000"):
            res = tool.execute(timezone=bad_offset)
            assert res.success is False
            assert "Unknown timezone" in (res.error or "")

    @patch("requests.get")
    def test_weather_tool_out_of_bounds_coordinates(self, mock_get: MagicMock) -> None:
        """Verify out-of-bounds latitude/longitude coordinates return clean error."""
        wttr_resp = MagicMock()
        wttr_resp.status_code = 500
        mock_get.return_value = wttr_resp

        tool = WeatherTool()
        res = tool.execute(location="95.0, 200.0")

        assert res.success is False
        assert "Invalid coordinates" in (res.error or "")
