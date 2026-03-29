"""Config-driven agent definitions and tool registry for Eddie.

Follows the same pattern as kindrent's Ray agent_configs.py:
- TOOLS_REGISTRY: defines available tools with Ollama function-calling schemas
- AGENT_CONFIGS: defines agent personalities with their whitelisted tools
"""

TOOLS_REGISTRY = {
    "get_current_time": {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current time. Optionally for a specific city/timezone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": (
                            "City name for timezone lookup (e.g. 'tokyo', 'new york'). "
                            "Defaults to London if not specified."
                        ),
                    }
                },
                "required": [],
            },
        },
    },
    "set_timer": {
        "type": "function",
        "function": {
            "name": "set_timer",
            "description": "Set a countdown timer for a specified duration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "duration": {
                        "type": "string",
                        "description": "Duration in natural language (e.g. '5 minutes', '2 hours', '30 seconds')",
                    },
                    "label": {
                        "type": "string",
                        "description": "Optional label for the timer (e.g. 'pasta', 'laundry')",
                    },
                },
                "required": ["duration"],
            },
        },
    },
    "cancel_timer": {
        "type": "function",
        "function": {
            "name": "cancel_timer",
            "description": "Cancel an active timer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Label of the timer to cancel. If not specified, cancels the most recent timer.",
                    }
                },
                "required": [],
            },
        },
    },
    "check_timer": {
        "type": "function",
        "function": {
            "name": "check_timer",
            "description": "Check how much time is remaining on an active timer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Label of the timer to check. If not specified, checks the most recent timer.",
                    }
                },
                "required": [],
            },
        },
    },
    "play_music": {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": "Play music on Spotify. Can play a specific song, artist, or album.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to play - a song name, artist name, or album name",
                    },
                    "artist": {
                        "type": "string",
                        "description": "Artist/band name if specified separately from the song",
                    },
                },
                "required": ["query"],
            },
        },
    },
    "pause_music": {
        "type": "function",
        "function": {
            "name": "pause_music",
            "description": "Pause the currently playing music.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    "skip_track": {
        "type": "function",
        "function": {
            "name": "skip_track",
            "description": "Skip to the next track.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    "get_weather": {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the weather forecast for a location and time period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Location name (e.g. 'home', 'cheltenham', 'york'). Defaults to 'home'.",
                    },
                    "time_period": {
                        "type": "string",
                        "description": (
                            "Time period like 'today', 'tomorrow', 'this morning', 'tonight', 'this afternoon'"
                        ),
                    },
                },
                "required": [],
            },
        },
    },
    "roll_dice": {
        "type": "function",
        "function": {
            "name": "roll_dice",
            "description": "Roll one or more dice with a specified number of sides.",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of dice to roll. Defaults to 1.",
                    },
                    "sides": {
                        "type": "integer",
                        "description": "Number of sides per die. Defaults to 6.",
                    },
                },
                "required": [],
            },
        },
    },
    "flip_coin": {
        "type": "function",
        "function": {
            "name": "flip_coin",
            "description": "Flip a coin and return heads or tails.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    "control_device": {
        "type": "function",
        "function": {
            "name": "control_device",
            "description": "Control a smart home device via MQTT (lights, heating, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "Device name or identifier",
                    },
                    "action": {
                        "type": "string",
                        "description": "Action to perform (e.g. 'on', 'off', 'set 22')",
                    },
                },
                "required": ["device", "action"],
            },
        },
    },
}

# Agent configurations - config-driven, just like kindrent's Ray
AGENT_CONFIGS = {
    "EDDIE_VOICE": {
        "model": "qwen2.5:14b",
        "system_instruction": (
            "You are Eddie, a friendly and helpful voice assistant. "
            "You run locally on the user's hardware - no data leaves their network. "
            "Keep responses concise and natural since they will be spoken aloud. "
            "Use the available tools to help with time, music, weather, timers, dice, and smart home control. "
            "If you don't have a tool for something, say so honestly."
        ),
        "tools": [
            TOOLS_REGISTRY["get_current_time"],
            TOOLS_REGISTRY["set_timer"],
            TOOLS_REGISTRY["cancel_timer"],
            TOOLS_REGISTRY["check_timer"],
            TOOLS_REGISTRY["play_music"],
            TOOLS_REGISTRY["pause_music"],
            TOOLS_REGISTRY["skip_track"],
            TOOLS_REGISTRY["get_weather"],
            TOOLS_REGISTRY["roll_dice"],
            TOOLS_REGISTRY["flip_coin"],
            TOOLS_REGISTRY["control_device"],
        ],
    },
}
