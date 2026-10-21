import requests


GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


WEATHER_CODES = {
    0: "clear",
    1: "mostly clear",
    2: "partly cloudy",
    3: "cloudy",
    45: "foggy",
    48: "foggy with possible icy fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    80: "light showers",
    81: "showers",
    82: "heavy showers",
    95: "thunderstorms",
}


def weather_code_text(code: int | None) -> str:
    if code is None:
        return "unknown conditions"

    return WEATHER_CODES.get(code, f"weather code {code}")


def geocode_location(lookup_name: str) -> dict:
    params = {
        "name": lookup_name,
        "count": 1,
        "language": "en",
        "format": "json",
    }

    response = requests.get(GEOCODE_URL, params=params, timeout=15)
    response.raise_for_status()

    data = response.json()
    results = data.get("results", [])

    if not results:
        raise RuntimeError(f"No geocoding result found for: {lookup_name}")

    result = results[0]

    return {
        "name": result.get("name"),
        "latitude": result["latitude"],
        "longitude": result["longitude"],
        "timezone": result.get("timezone", "America/Los_Angeles"),
        "admin1": result.get("admin1"),
        "country": result.get("country"),
    }


def get_forecast(latitude: float, longitude: float, timezone: str = "America/Los_Angeles", *, days: int = 1) -> dict:
    if type(days) is not int or not 1 <= days <= 7:
        raise ValueError("Forecast range must be 1–7 days.")
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m,wind_gusts_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_gusts_10m_max,weather_code",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": timezone,
        "forecast_days": days,
    }

    response = requests.get(FORECAST_URL, params=params, timeout=15)
    response.raise_for_status()

    return response.json()


def build_weather_summary(forecast: dict, display_label: str) -> str:
    current = forecast.get("current", {})
    daily = forecast.get("daily", {})

    temp = current.get("temperature_2m")
    feels = current.get("apparent_temperature")
    condition = weather_code_text(current.get("weather_code"))
    wind = current.get("wind_speed_10m")
    gusts = current.get("wind_gusts_10m")
    rain_now = current.get("rain") or 0
    precip_today = (daily.get("precipitation_sum") or [0])[0]
    high = (daily.get("temperature_2m_max") or [None])[0]
    low = (daily.get("temperature_2m_min") or [None])[0]

    alerts = []

    if rain_now > 0 or precip_today >= 0.03 or "rain" in condition or "showers" in condition:
        alerts.append("roads may be wet")

    if gusts is not None and gusts >= 25:
        alerts.append("watch the wind gusts")

    if temp is not None and temp <= 35:
        alerts.append("watch for cold spots")

    if "fog" in condition:
        alerts.append("visibility may be lower")

    if temp is None:
        return f"Weather {display_label}: weather data is unavailable right now."

    summary = f"Weather {display_label}: {round(temp)} degrees, {condition}"

    if feels is not None and abs(feels - temp) >= 5:
        summary += f", feels like {round(feels)}"

    if high is not None and low is not None:
        summary += f". High {round(high)}, low {round(low)}"

    if wind is not None:
        summary += f". Wind around {round(wind)} miles per hour"

    if alerts:
        summary += ". " + ", ".join(alerts) + "."

    return summary


def get_weather_for_location(location: dict, *, forecast_days: int = 1) -> dict:
    lookup_name = location.get("lookup_name")
    display_label = location.get("display_label", lookup_name)

    latitude = location.get("latitude")
    longitude = location.get("longitude")
    timezone = "America/Los_Angeles"

    if latitude is None or longitude is None:
        geocoded = geocode_location(lookup_name)
        latitude = geocoded["latitude"]
        longitude = geocoded["longitude"]
        timezone = geocoded.get("timezone") or timezone
    else:
        geocoded = {
            "name": location.get("name"),
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
        }

    forecast = get_forecast(latitude, longitude, timezone, days=forecast_days)
    summary = build_weather_summary(forecast, display_label)

    return {
        "location": location,
        "geocoded": geocoded,
        "forecast": forecast,
        "summary": summary,
    }
