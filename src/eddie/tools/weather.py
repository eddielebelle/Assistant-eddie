"""Weather tool for Eddie."""

import logging
from datetime import datetime, timedelta

import pyowm
import pytz
from dateutil.tz import tzlocal

from eddie.config import get_config

logger = logging.getLogger(__name__)


class WeatherManager:
    """Weather forecasting via OpenWeatherMap."""

    def __init__(self) -> None:
        config = get_config()
        self.locations = config.weather_locations
        self.uk_time = pytz.timezone("Europe/London")

        try:
            self.owm = pyowm.OWM(config.openweather_api_key)
            self.mgr = self.owm.weather_manager()
        except Exception:
            logger.exception("Failed to initialize OpenWeatherMap client")
            self.mgr = None

    def get_weather(self, location: str = "home", time_period: str = "") -> str:
        """Get weather forecast for a location and time period."""
        if not self.mgr:
            return "Weather service is not configured."

        location = location.lower().strip()
        if location not in self.locations:
            return f"I don't have location data for '{location}'. Available: {', '.join(self.locations.keys())}"

        start_hour, end_hour = self._parse_time_period(time_period)
        forecast = self._get_hourly_forecast(location, start_hour, end_hour)

        if not forecast:
            return f"No forecast data available for {location}."

        # Group consecutive hours with same weather
        groups = self._group_forecast(forecast)

        # Build response from ALL groups (fixed bug: old code only returned first)
        parts = []
        for group in groups:
            parts.append(
                f"From {group['start']} to {group['end']}: {group['weather']}, "
                f"high of {group['high_temp']}°C, {group['avg_rain']}% chance of rain"
            )

        return f"Weather for {location.title()}: " + ". ".join(parts) + "."

    def _parse_time_period(self, text: str) -> tuple[datetime, datetime]:
        """Parse a time period string into start/end datetimes."""
        now = datetime.now(tzlocal()).replace(hour=0, minute=0, second=0, microsecond=0)

        dates = {
            "today": timedelta(days=0),
            "this": timedelta(days=0),
            "tomorrow": timedelta(days=1),
            "week": timedelta(days=7),
        }
        times = {
            "morning": (timedelta(hours=6), timedelta(hours=11, minutes=59, seconds=59)),
            "afternoon": (timedelta(hours=12), timedelta(hours=17, minutes=59, seconds=59)),
            "evening": (timedelta(hours=18), timedelta(hours=21, minutes=59, seconds=59)),
            "night": (timedelta(hours=22), timedelta(hours=5)),
            "tonight": (timedelta(hours=22), timedelta(hours=5)),
        }

        text = text.lower()
        date_adjusted = False
        time_adjusted = False

        for key, delta in dates.items():
            if key in text:
                now = (now + delta).replace(hour=0, minute=0, second=0, microsecond=0)
                date_adjusted = True

        start_time = now
        end_time = now

        for key, (start_delta, end_delta) in times.items():
            if key in text:
                start_time = now + start_delta
                end_time = now + end_delta
                time_adjusted = True
                if end_time < start_time:
                    end_time += timedelta(days=1)
                break

        if date_adjusted and not time_adjusted:
            end_time = end_time.replace(hour=23, minute=59, second=59)

        if not date_adjusted and not time_adjusted:
            # Default: next 4 hours from now
            start_time = datetime.now(tzlocal())
            end_time = start_time + timedelta(hours=4)

        return start_time, end_time

    def _get_hourly_forecast(self, location: str, start_hour: datetime, end_hour: datetime) -> list[dict]:
        """Fetch and filter hourly forecast data."""
        coords = self.locations[location]

        try:
            one_call = self.mgr.one_call(coords["lat"], coords["lon"], units="metric", timezone=self.uk_time)
        except Exception:
            logger.exception("Failed to fetch weather data")
            return []

        hourly_raw = [w.to_dict() for w in one_call.forecast_hourly]
        filtered = [h for h in hourly_raw if start_hour.timestamp() <= h["reference_time"] <= end_hour.timestamp()]

        result = []
        for h in filtered:
            rain_pct = int(h.get("precipitation_probability", 0) * 100)
            result.append(
                {
                    "time": datetime.fromtimestamp(h["reference_time"]).strftime("%H:%M"),
                    "weather": self._simplify_weather(h.get("detailed_status", "")),
                    "temperature": h.get("temperature", {}).get("temp", 0),
                    "rain_percent": rain_pct,
                    "humidity": h.get("humidity", 0),
                    "wind_speed": h.get("wind", {}).get("speed", 0),
                }
            )

        return result

    def _group_forecast(self, forecast: list[dict]) -> list[dict]:
        """Group consecutive hours with the same weather condition."""
        if not forecast:
            return []

        groups = []
        current = {
            "start": forecast[0]["time"],
            "end": forecast[0]["time"],
            "weather": forecast[0]["weather"],
            "temps": [forecast[0]["temperature"]],
            "rain_pcts": [forecast[0]["rain_percent"]],
        }

        for hour in forecast[1:]:
            if hour["weather"] == current["weather"]:
                current["end"] = hour["time"]
                current["temps"].append(hour["temperature"])
                current["rain_pcts"].append(hour["rain_percent"])
            else:
                groups.append(self._finalize_group(current))
                current = {
                    "start": hour["time"],
                    "end": hour["time"],
                    "weather": hour["weather"],
                    "temps": [hour["temperature"]],
                    "rain_pcts": [hour["rain_percent"]],
                }

        groups.append(self._finalize_group(current))
        return groups

    @staticmethod
    def _finalize_group(group: dict) -> dict:
        return {
            "start": group["start"],
            "end": group["end"],
            "weather": group["weather"],
            "high_temp": round(max(group["temps"]), 1),
            "avg_rain": round(sum(group["rain_pcts"]) / len(group["rain_pcts"])),
        }

    @staticmethod
    def _simplify_weather(desc: str) -> str:
        """Simplify detailed weather description."""
        desc = desc.lower()
        if "thunder" in desc:
            return "stormy"
        if "snow" in desc:
            return "snowy"
        if "clear" in desc:
            return "clear"
        if "drizzle" in desc:
            return "drizzly"
        if "rain" in desc:
            return "rainy"
        if "cloud" in desc:
            return "cloudy"
        return desc
