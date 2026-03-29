"""Eddie Agent Service - Flask app with Ollama tool-calling loop.

Core pattern from kindrent's Ray: config-driven agent with tool-calling loop.
Instead of Gemini, uses a local LLM via Ollama with native function calling.
"""

import logging

import ollama
from flask import Flask, jsonify, request

from eddie.agent.agent_configs import AGENT_CONFIGS
from eddie.agent.conversation import ConversationManager
from eddie.agent.tool_executor import execute_tool
from eddie.agent.tool_state import ToolStateManager
from eddie.config import get_config

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global state
config = get_config()
conversation = ConversationManager(
    max_messages=config.max_history_messages,
    idle_timeout=config.session_idle_timeout,
)
tool_state = ToolStateManager()


def _build_system_prompt(agent_config: dict) -> str:
    """Build system prompt with active tool state injected."""
    base = agent_config["system_instruction"]
    state_summary = tool_state.get_state_summary()
    if state_summary:
        return f"{base}\n\n{state_summary}"
    return base


def chat(user_text: str, agent_name: str = "EDDIE_VOICE") -> str:
    """Process a user message through the tool-calling agent loop.

    This is the core loop - same pattern as kindrent's Ray:
    1. Send user message + tools to LLM
    2. If LLM wants to call a tool, execute it and feed result back
    3. Repeat until LLM has a final text response
    """
    agent_config = AGENT_CONFIGS[agent_name]
    model = config.ollama_model or agent_config.get("model", "qwen2.5:14b")
    tools = agent_config["tools"]

    # Add user message to conversation history
    conversation.add_message("user", user_text)

    # Build messages with system prompt (includes active tool state)
    system_prompt = _build_system_prompt(agent_config)
    messages = conversation.get_messages(system_prompt)

    # Ollama tool-calling loop
    response = ollama.chat(
        model=model,
        messages=messages,
        tools=tools,
    )

    # Loop while the model wants to call tools
    while response.message.tool_calls:
        # Add the assistant's tool-call message to history
        conversation.add_raw(response.message.model_dump())

        for tool_call in response.message.tool_calls:
            tool_name = tool_call.function.name
            arguments = tool_call.function.arguments or {}

            logger.info("LLM requested tool: %s(%s)", tool_name, arguments)

            # Execute the tool
            result = execute_tool(tool_name, arguments)

            # Add tool response to history
            conversation.add_raw(
                {
                    "role": "tool",
                    "content": result,
                }
            )

        # Send updated history back to the model
        messages = conversation.get_messages(system_prompt)
        response = ollama.chat(
            model=model,
            messages=messages,
            tools=tools,
        )

    # Final text response from the model
    assistant_text = response.message.content
    conversation.add_message("assistant", assistant_text)

    logger.info("Eddie response: %s", assistant_text[:200])
    return assistant_text


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """HTTP endpoint for the agent service."""
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "Missing 'text' field"}), 400

    user_text = data["text"]
    agent_name = data.get("agent", "EDDIE_VOICE")

    try:
        response_text = chat(user_text, agent_name)
        return jsonify({"response": response_text})
    except Exception:
        logger.exception("Error processing chat request")
        return jsonify({"error": "Internal error processing your request"}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


def main():
    """Entry point for eddie-agent command."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logger.info("Starting Eddie Agent on port %d (model: %s)", config.agent_port, config.ollama_model)
    app.run(host="0.0.0.0", port=config.agent_port, debug=False)


if __name__ == "__main__":
    main()
