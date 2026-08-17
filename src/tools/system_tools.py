"""Time and weather tools for Friday."""

from __future__ import annotations

import datetime
import logging
import re
import unicodedata
import urllib.parse
import zoneinfo
from typing import Any

import requests

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# WMO Weather interpretation codes (WW) for Open-Meteo fallback
WMO_WEATHER_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    62: "Moderate rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

# Common timezone abbreviations mapping to IANA names
COMMON_TZ_ALIASES: dict[str, str] = {
    "UTC": "UTC",
    "GMT": "GMT",
    "Z": "UTC",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "BST": "Europe/London",
    "CET": "Europe/Paris",
    "CEST": "Europe/Paris",
    "JST": "Asia/Tokyo",
    "KST": "Asia/Seoul",
    "IST": "Asia/Kolkata",
    "MSK": "Europe/Moscow",
}


def _resolve_timezone(tz_input: str) -> tuple[datetime.tzinfo, str] | None:
    """Resolve a timezone input string into a tzinfo object and display label."""
    s = tz_input.strip()
    s_upper = s.upper()

    if s_upper in ("UTC", "GMT", "Z"):
        return datetime.UTC, "UTC"

    if s_upper in COMMON_TZ_ALIASES:
        iana = COMMON_TZ_ALIASES[s_upper]
        return zoneinfo.ZoneInfo(iana), f"{s_upper} / {iana}"

    # UTC / GMT offset formats: UTC+3, GMT-5:30, +04:00, -0800
    offset_match = re.match(r"^(?:UTC|GMT)?\s*([+-])(\d{1,2})(?::?(\d{2}))?$", s_upper)
    if offset_match:
        try:
            sign = 1 if offset_match.group(1) == "+" else -1
            hours = int(offset_match.group(2))
            mins = int(offset_match.group(3) or 0)
            if hours <= 23 and mins <= 59:
                td = datetime.timedelta(hours=sign * hours, minutes=sign * mins)
                disp = f"UTC{offset_match.group(1)}{hours:02d}:{mins:02d}"
                return datetime.timezone(td, name=disp), disp
        except Exception:
            pass

    # Direct ZoneInfo attempt
    try:
        return zoneinfo.ZoneInfo(s), s
    except Exception:
        pass

    # Case-insensitive / normalized lookup in available timezones
    try:
        available = zoneinfo.available_timezones()
        low_map = {tz.lower(): tz for tz in available}
        s_norm = s.lower().replace(" ", "_")

        if s_norm in low_map:
            iana = low_map[s_norm]
            return zoneinfo.ZoneInfo(iana), iana

        # Match city or region suffix (e.g. "tokyo" -> "Asia/Tokyo")
        city_matches = [tz for tz in available if tz.lower().endswith(f"/{s_norm}")]
        if city_matches:
            iana = sorted(city_matches)[0]
            return zoneinfo.ZoneInfo(iana), iana
    except Exception:
        pass

    return None


class TimeTool(BaseTool):
    """Tool to get the current date, time, and timezone."""

    @property
    def name(self) -> str:
        return "get_current_time"

    @property
    def description(self) -> str:
        return (
            "Get the current local or timezone-specific date and time, "
            "including day of the week, timezone name, offset, and ISO timestamp."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": (
                        "Optional IANA timezone name or abbreviation (e.g. 'UTC', 'America/New_York', "
                        "'Europe/London', 'Asia/Tokyo', 'EST', 'PST', 'UTC+3'). "
                        "Defaults to the system local timezone."
                    ),
                },
            },
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the time tool.

        Args:
            timezone: Optional timezone string.

        Returns:
            ToolResult with formatted date and time information.
        """
        tz_name = kwargs.get("timezone")

        try:
            if tz_name and str(tz_name).strip():
                tz_clean = str(tz_name).strip()
                resolved = _resolve_timezone(tz_clean)
                if resolved is None:
                    return ToolResult(
                        success=False,
                        error=(
                            f"Unknown timezone: '{tz_clean}'. Please provide a valid IANA "
                            "timezone name (e.g., 'UTC', 'America/New_York', 'Europe/London', 'Asia/Tokyo', 'PST', 'UTC+3')."
                        ),
                    )
                tz_obj, tz_label = resolved
                now = datetime.datetime.now(tz=tz_obj)
                tz_display = f"{tz_label} (UTC{now.strftime('%z')})"
            else:
                now = datetime.datetime.now().astimezone()
                tz_display = f"Local ({now.tzname() or 'UTC'}, UTC{now.strftime('%z')})"

            formatted_output = (
                f"Current Date and Time:\n"
                f"- Date: {now.strftime('%A, %B %d, %Y')}\n"
                f"- Time: {now.strftime('%H:%M:%S')}\n"
                f"- Day of Week: {now.strftime('%A')}\n"
                f"- Timezone: {tz_display}\n"
                f"- ISO 8601: {now.isoformat()}"
            )

            return ToolResult(success=True, output=formatted_output)

        except Exception as exc:
            logger.exception("Error in TimeTool")
            return ToolResult(
                success=False,
                error=f"Failed to get current time: {exc}",
            )


class WeatherTool(BaseTool):
    """Tool to fetch weather information for a location."""

    def __init__(self, timeout: int = 10) -> None:
        """Initialize WeatherTool.

        Args:
            timeout: Network request timeout in seconds (default: 10).
        """
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "get_weather"

    @property
    def description(self) -> str:
        return (
            "Fetch the current weather and forecast for any city or location "
            "using public weather services (wttr.in / Open-Meteo)."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": (
                        "City name, region, or latitude,longitude coordinates "
                        "(e.g. 'London', 'San Francisco', 'Tokyo', 'Berlin', '40.7128,-74.0060')."
                    ),
                },
                "format": {
                    "type": "string",
                    "enum": ["summary", "detailed"],
                    "description": (
                        "Output format: 'summary' for current conditions, "
                        "'detailed' for current conditions + 3-day forecast (default: 'summary')."
                    ),
                },
            },
            "required": ["location"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute weather lookup.

        Args:
            location: City or place name or coordinates.
            format: 'summary' or 'detailed'.

        Returns:
            ToolResult containing weather details or error.
        """
        location = kwargs.get("location")
        if not location or not str(location).strip():
            return ToolResult(
                success=False, error="Missing required parameter: location"
            )

        loc_str = str(location).strip()
        format_type = str(kwargs.get("format", "summary")).strip().lower()

        # 1. Try wttr.in JSON API first
        wttr_result = self._fetch_wttr_in(loc_str, format_type)
        if wttr_result is not None:
            return wttr_result

        # 2. Fallback to Open-Meteo
        logger.info("wttr.in unavailable or failed, falling back to Open-Meteo")
        open_meteo_result = self._fetch_open_meteo(loc_str, format_type)
        if open_meteo_result is not None:
            return open_meteo_result

        return ToolResult(
            success=False,
            error=f"Could not retrieve weather data for '{loc_str}'. Please check the location name.",
        )

    def _fetch_wttr_in(self, location: str, format_type: str) -> ToolResult | None:
        """Fetch weather data from wttr.in."""
        try:
            encoded_loc = urllib.parse.quote(location)
            url = f"https://wttr.in/{encoded_loc}?format=j1"
            headers = {"User-Agent": "Friday-Desktop-Assistant/1.0"}

            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code != 200:
                return None

            data = response.json()
            current_list = data.get("current_condition", [])
            if not current_list:
                return None

            curr = current_list[0]
            nearest_area_list = data.get("nearest_area", [])
            area_name = location
            country_name = ""
            if nearest_area_list:
                area_obj = nearest_area_list[0]
                area_val = area_obj.get("areaName", [{}])[0].get("value")
                country_val = area_obj.get("country", [{}])[0].get("value")
                if area_val:
                    area_name = area_val
                if country_val:
                    country_name = f", {country_val}"

            temp_c = curr.get("temp_C", "N/A")
            temp_f = curr.get("temp_F", "N/A")
            feels_c = curr.get("FeelsLikeC", "N/A")
            feels_f = curr.get("FeelsLikeF", "N/A")
            humidity = curr.get("humidity", "N/A")
            wind_kmph = curr.get("windspeedKmph", "N/A")
            wind_dir = curr.get("winddir16Point", "")
            uv_index = curr.get("uvIndex", "N/A")
            precip_mm = curr.get("precipMM", "0.0")

            desc_list = curr.get("weatherDesc", [])
            weather_desc = (
                desc_list[0].get("value", "Unknown") if desc_list else "Unknown"
            )

            lines = [
                f"Weather for {area_name}{country_name}:",
                f"- Condition: {weather_desc}",
                f"- Temperature: {temp_c}°C ({temp_f}°F)",
                f"- Feels Like: {feels_c}°C ({feels_f}°F)",
                f"- Humidity: {humidity}%",
                f"- Wind: {wind_kmph} km/h {wind_dir}".strip(),
                f"- Precipitation: {precip_mm} mm",
                f"- UV Index: {uv_index}",
            ]

            if format_type == "detailed":
                forecast_list = data.get("weather", [])
                if forecast_list:
                    lines.append("\n3-Day Forecast:")
                    for day in forecast_list[:3]:
                        date = day.get("date", "N/A")
                        max_c = day.get("maxtempC", "N/A")
                        min_c = day.get("mintempC", "N/A")
                        max_f = day.get("maxtempF", "N/A")
                        min_f = day.get("mintempF", "N/A")
                        astronomy = day.get("astronomy", [{}])[0]
                        sunrise = astronomy.get("sunrise", "N/A")
                        sunset = astronomy.get("sunset", "N/A")

                        # Get mid-day weather description
                        hourly = day.get("hourly", [])
                        mid_desc = "Variable"
                        if hourly:
                            mid_hour = hourly[len(hourly) // 2]
                            h_desc = mid_hour.get("weatherDesc", [])
                            if h_desc:
                                mid_desc = h_desc[0].get("value", "Variable")

                        lines.append(
                            f"  * {date}: {mid_desc} | High: {max_c}°C ({max_f}°F), "
                            f"Low: {min_c}°C ({min_f}°F) | Sunrise: {sunrise}, Sunset: {sunset}"
                        )

            return ToolResult(success=True, output="\n".join(lines))

        except Exception as exc:
            logger.warning(f"wttr.in fetch error: {exc}")
            return None

    def _fetch_open_meteo(self, location: str, format_type: str) -> ToolResult | None:
        """Fetch weather data from Open-Meteo API as fallback."""
        try:
            lat: float | None = None
            lon: float | None = None
            place_name = location
            country_str = ""

            # Check if location is already formatted as coordinates: "lat, lon"
            coord_match = re.match(
                r"^\s*([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)\s*$", location
            )
            if coord_match:
                lat = float(coord_match.group(1))
                lon = float(coord_match.group(2))
                place_name = f"Coordinates ({lat}, {lon})"
            else:
                # Geocode location using Open-Meteo geocoding API with multi-tier queries
                geo_queries = [
                    f"name={urllib.parse.quote(location)}&count=1&language=en&format=json",
                    f"name={urllib.parse.quote(location)}&count=1&format=json",
                ]

                # If non-ASCII, also add normalized ASCII query
                normalized = (
                    unicodedata.normalize("NFKD", location)
                    .encode("ascii", "ignore")
                    .decode("ascii")
                    .strip()
                )
                if normalized and normalized.lower() != location.lower():
                    geo_queries.append(
                        f"name={urllib.parse.quote(normalized)}&count=1&format=json"
                    )

                results = None
                for q in geo_queries:
                    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?{q}"
                    geo_resp = requests.get(geo_url, timeout=self.timeout)
                    if geo_resp.status_code == 200:
                        geo_data = geo_resp.json()
                        cand_results = geo_data.get("results", [])
                        if cand_results:
                            results = cand_results
                            break

                if not results:
                    return ToolResult(
                        success=False,
                        error=f"Could not find location coordinates for '{location}'.",
                    )

                place = results[0]
                lat = place.get("latitude")
                lon = place.get("longitude")
                place_name = place.get("name", location)
                country = place.get("country", "")
                country_str = f", {country}" if country else ""

            if lat is None or lon is None:
                return None

            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                return ToolResult(
                    success=False,
                    error=f"Invalid coordinates ({lat}, {lon}): latitude must be between -90 and 90, longitude between -180 and 180.",
                )

            # Fetch forecast
            weather_url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}&"
                f"current=temperature_2m,relative_humidity_2m,apparent_temperature,"
                f"precipitation,weather_code,wind_speed_10m&"
                f"daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset&"
                f"timezone=auto"
            )
            w_resp = requests.get(weather_url, timeout=self.timeout)
            if w_resp.status_code != 200:
                return None

            w_data = w_resp.json()
            current = w_data.get("current", {})
            temp_c = current.get("temperature_2m", "N/A")
            feels_c = current.get("apparent_temperature", "N/A")
            humidity = current.get("relative_humidity_2m", "N/A")
            wind_kmh = current.get("wind_speed_10m", "N/A")
            precip = current.get("precipitation", "0.0")
            code = current.get("weather_code", 0)
            condition = WMO_WEATHER_CODES.get(code, "Unknown")

            temp_f: float | str
            feels_f: float | str
            try:
                temp_f = round(float(temp_c) * 9 / 5 + 32, 1)
                feels_f = round(float(feels_c) * 9 / 5 + 32, 1)
            except (ValueError, TypeError):
                temp_f = "N/A"
                feels_f = "N/A"

            lines = [
                f"Weather for {place_name}{country_str}:",
                f"- Condition: {condition}",
                f"- Temperature: {temp_c}°C ({temp_f}°F)",
                f"- Feels Like: {feels_c}°C ({feels_f}°F)",
                f"- Humidity: {humidity}%",
                f"- Wind: {wind_kmh} km/h",
                f"- Precipitation: {precip} mm",
            ]

            if format_type == "detailed":
                daily = w_data.get("daily", {})
                dates = daily.get("time", [])
                max_temps = daily.get("temperature_2m_max", [])
                min_temps = daily.get("temperature_2m_min", [])
                codes = daily.get("weather_code", [])
                sunrises = daily.get("sunrise", [])
                sunsets = daily.get("sunset", [])

                if dates:
                    lines.append("\nForecast:")
                    for i in range(min(3, len(dates))):
                        d = dates[i]
                        high = max_temps[i] if i < len(max_temps) else "N/A"
                        low = min_temps[i] if i < len(min_temps) else "N/A"
                        c_code = codes[i] if i < len(codes) else 0
                        cond = WMO_WEATHER_CODES.get(c_code, "Variable")
                        sr = sunrises[i].split("T")[-1] if i < len(sunrises) else "N/A"
                        ss = sunsets[i].split("T")[-1] if i < len(sunsets) else "N/A"

                        high_str = f"{high}°C"
                        try:
                            high_f = round(float(high) * 9 / 5 + 32, 1)
                            high_str = f"{high}°C ({high_f}°F)"
                        except (ValueError, TypeError):
                            pass

                        low_str = f"{low}°C"
                        try:
                            low_f = round(float(low) * 9 / 5 + 32, 1)
                            low_str = f"{low}°C ({low_f}°F)"
                        except (ValueError, TypeError):
                            pass

                        lines.append(
                            f"  * {d}: {cond} | High: {high_str}, Low: {low_str} | Sunrise: {sr}, Sunset: {ss}"
                        )

            return ToolResult(success=True, output="\n".join(lines))

        except Exception as exc:
            logger.warning(f"Open-Meteo fetch error: {exc}")
            return None
