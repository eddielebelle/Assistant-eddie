"""Tool dispatcher for Eddie agent.

Maps tool names from LLM function calls to actual implementations.
Follows the same dispatcher pattern as kindrent's Ray tool_executor.py.
"""

import logging

from eddie.tools import clock, dice, music, smart_home, timer, weather

logger = logging.getLogger(__name__)

# Tool state holders (initialized once, shared across calls)
_music_mgr: music.MusicManager | None = None
_timer_mgr: timer.TimerManager | None = None
_weather_mgr: weather.WeatherManager | None = None


def _get_music_manager() -> music.MusicManager:
    global _music_mgr
    if _music_mgr is None:
        _music_mgr = music.MusicManager()
    return _music_mgr


def _get_timer_manager() -> timer.TimerManager:
    global _timer_mgr
    if _timer_mgr is None:
        _timer_mgr = timer.TimerManager()
    return _timer_mgr


def _get_weather_manager() -> weather.WeatherManager:
    global _weather_mgr
    if _weather_mgr is None:
        _weather_mgr = weather.WeatherManager()
    return _weather_mgr


# Dispatcher mapping: tool name -> handler function
TOOL_DISPATCHER: dict[str, callable] = {
    "get_current_time": lambda **kwargs: clock.get_current_time(**kwargs),
    "set_timer": lambda **kwargs: _get_timer_manager().set_timer(**kwargs),
    "cancel_timer": lambda **kwargs: _get_timer_manager().cancel_timer(**kwargs),
    "check_timer": lambda **kwargs: _get_timer_manager().check_timer(**kwargs),
    "play_music": lambda **kwargs: _get_music_manager().play(**kwargs),
    "pause_music": lambda **kwargs: _get_music_manager().pause(),
    "skip_track": lambda **kwargs: _get_music_manager().skip(),
    "get_weather": lambda **kwargs: _get_weather_manager().get_weather(**kwargs),
    "roll_dice": lambda **kwargs: dice.roll_dice(**kwargs),
    "flip_coin": lambda **kwargs: dice.flip_coin(),
    "control_device": lambda **kwargs: smart_home.control_device(**kwargs),
}


def execute_tool(tool_name: str, arguments: dict) -> str:
    """Execute a tool by name with the given arguments.

    Returns a string result that gets sent back to the LLM.
    """
    if tool_name not in TOOL_DISPATCHER:
        logger.warning("Unknown tool requested: %s", tool_name)
        return f"Error: Unknown tool '{tool_name}'"

    try:
        logger.info("Executing tool: %s(%s)", tool_name, arguments)
        result = TOOL_DISPATCHER[tool_name](**arguments)
        logger.info("Tool %s returned: %s", tool_name, str(result)[:200])
        return str(result)
    except Exception:
        logger.exception("Error executing tool '%s'", tool_name)
        return f"Error executing tool '{tool_name}'. Please try again."
