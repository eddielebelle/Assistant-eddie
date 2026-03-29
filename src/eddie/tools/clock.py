"""Clock and timezone tool for Eddie."""

import logging
from datetime import datetime

import pytz

from eddie.tools.timezones import TIMEZONES

logger = logging.getLogger(__name__)


def get_current_time(city: str = "london") -> str:
    """Get the current time for a given city.

    Returns a human-readable time string.
    """
    city = city.lower().strip()

    zone_name = TIMEZONES.get(city)
    if not zone_name:
        return f"I don't have timezone data for '{city}'. Try a major city name."

    try:
        tz = pytz.timezone(zone_name)
    except pytz.exceptions.UnknownTimeZoneError:
        return f"Unknown timezone '{zone_name}' for city '{city}'."

    now = datetime.now(tz)
    hour = now.strftime("%-I")
    minutes = now.minute
    am_pm = now.strftime("%p").lower()

    if minutes == 0:
        time_str = f"{hour} o'clock"
    elif minutes == 15:
        time_str = f"quarter past {hour}"
    elif minutes == 30:
        time_str = f"half past {hour}"
    elif minutes == 45:
        next_hour = (now.hour % 12) + 1
        if next_hour == 0:
            next_hour = 12
        time_str = f"quarter to {next_hour}"
    elif minutes < 30:
        time_str = f"{minutes} minutes past {hour}"
    else:
        next_hour = (now.hour % 12) + 1
        if next_hour == 0:
            next_hour = 12
        time_str = f"{60 - minutes} minutes to {next_hour}"

    return f"The time in {city.title()} is {time_str} {am_pm}."
