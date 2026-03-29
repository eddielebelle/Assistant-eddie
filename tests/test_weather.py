"""Tests for the weather tool (parsing only - no API calls)."""

from eddie.tools.weather import WeatherManager


class TestSimplifyWeather:
    def test_thunder(self):
        assert WeatherManager._simplify_weather("thunderstorm with light rain") == "stormy"

    def test_snow(self):
        assert WeatherManager._simplify_weather("light snow") == "snowy"

    def test_clear(self):
        assert WeatherManager._simplify_weather("clear sky") == "clear"

    def test_drizzle(self):
        assert WeatherManager._simplify_weather("light drizzle") == "drizzly"

    def test_rain(self):
        assert WeatherManager._simplify_weather("moderate rain") == "rainy"

    def test_cloud(self):
        assert WeatherManager._simplify_weather("overcast clouds") == "cloudy"

    def test_passthrough(self):
        assert WeatherManager._simplify_weather("mist") == "mist"


class TestGroupForecast:
    def test_single_group(self):
        forecast = [
            {"time": "09:00", "weather": "cloudy", "temperature": 15, "rain_percent": 20},
            {"time": "10:00", "weather": "cloudy", "temperature": 16, "rain_percent": 25},
        ]
        mgr = WeatherManager.__new__(WeatherManager)
        groups = mgr._group_forecast(forecast)
        assert len(groups) == 1
        assert groups[0]["weather"] == "cloudy"
        assert groups[0]["high_temp"] == 16
        assert groups[0]["avg_rain"] == 22  # (20+25)/2 rounded

    def test_multiple_groups(self):
        forecast = [
            {"time": "09:00", "weather": "cloudy", "temperature": 15, "rain_percent": 20},
            {"time": "10:00", "weather": "rainy", "temperature": 14, "rain_percent": 80},
            {"time": "11:00", "weather": "rainy", "temperature": 13, "rain_percent": 90},
        ]
        mgr = WeatherManager.__new__(WeatherManager)
        groups = mgr._group_forecast(forecast)
        assert len(groups) == 2
        assert groups[0]["weather"] == "cloudy"
        assert groups[1]["weather"] == "rainy"
        assert groups[1]["high_temp"] == 14
        assert groups[1]["avg_rain"] == 85

    def test_empty_forecast(self):
        mgr = WeatherManager.__new__(WeatherManager)
        groups = mgr._group_forecast([])
        assert groups == []
