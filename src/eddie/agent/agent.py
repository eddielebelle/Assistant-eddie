"""Eddie Agent Service - Flask app with Ollama tool-calling loop.

Core pattern from kindrent's Ray: config-driven agent with tool-calling loop.
Instead of Gemini, uses a local LLM via Ollama with native function calling.
"""

import logging

import ollama
from flask import Flask, Response, jsonify, request, render_template_string

from eddie.agent.agent_configs import AGENT_CONFIGS
from eddie.agent.conversation import ConversationManager
from eddie.agent import events
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
    events.emit("user_input", {"text": user_text})

    # Build messages with system prompt (includes active tool state)
    system_prompt = _build_system_prompt(agent_config)
    messages = conversation.get_messages(system_prompt)

    # Ollama tool-calling loop
    events.emit("llm_start", {"model": model})
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
            events.emit("tool_call", {"tool": tool_name, "args": arguments})

            # Execute the tool
            result = execute_tool(tool_name, arguments)
            events.emit("tool_result", {"tool": tool_name, "result": result[:500]})

            # Add tool response to history
            conversation.add_raw(
                {
                    "role": "tool",
                    "content": result,
                }
            )

        # Send updated history back to the model
        messages = conversation.get_messages(system_prompt)
        events.emit("llm_start", {"model": model})
        response = ollama.chat(
            model=model,
            messages=messages,
            tools=tools,
        )

    # Final text response from the model
    assistant_text = response.message.content
    conversation.add_message("assistant", assistant_text)
    events.emit("response", {"text": assistant_text})

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


@app.route("/api/events")
def event_stream():
    """SSE endpoint for real-time monitoring."""
    q = events.subscribe()

    def generate():
        try:
            yield from events.stream_sse(q)
        finally:
            events.unsubscribe(q)

    return Response(generate(), mimetype="text/event-stream")


@app.route("/monitor")
def monitor():
    """Live monitoring dashboard."""
    return render_template_string(MONITOR_HTML)


MONITOR_HTML = r"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Eddie Monitor</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0a0a0a; color: #d4d4d4; font-family: 'Menlo', 'Consolas', monospace;
         font-size: 14px; padding: 20px; }
  h1 { color: #7aa2f7; margin-bottom: 16px; font-size: 18px; }
  .status { color: #565f89; margin-bottom: 16px; }
  .status .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
                 background: #9ece6a; margin-right: 6px; }
  #log { max-height: calc(100vh - 80px); overflow-y: auto; }
  .event { padding: 8px 12px; border-left: 3px solid #565f89; margin-bottom: 4px;
           background: #1a1b26; border-radius: 0 4px 4px 0; }
  .event .time { color: #565f89; font-size: 12px; }
  .event.user_input { border-color: #7aa2f7; }
  .event.user_input .label { color: #7aa2f7; }
  .event.llm_start { border-color: #e0af68; }
  .event.llm_start .label { color: #e0af68; }
  .event.tool_call { border-color: #bb9af7; }
  .event.tool_call .label { color: #bb9af7; }
  .event.tool_result { border-color: #9ece6a; }
  .event.tool_result .label { color: #9ece6a; }
  .event.response { border-color: #73daca; }
  .event.response .label { color: #73daca; }
  .event .body { margin-top: 4px; white-space: pre-wrap; word-break: break-word; }
</style>
</head><body>
<h1>Eddie Monitor</h1>
<div class="status"><span class="dot" id="dot"></span><span id="status">connecting...</span></div>
<div id="log"></div>
<script>
const log = document.getElementById('log');
const dot = document.getElementById('dot');
const status = document.getElementById('status');
const labels = {
  user_input: 'INPUT',
  llm_start:  'LLM',
  tool_call:  'TOOL',
  tool_result:'RESULT',
  response:   'OUTPUT'
};

function formatBody(e) {
  switch(e.type) {
    case 'user_input': return e.text;
    case 'llm_start':  return 'Processing with ' + e.model + '...';
    case 'tool_call':  return e.tool + '(' + JSON.stringify(e.args) + ')';
    case 'tool_result':return e.tool + ' → ' + e.result;
    case 'response':   return e.text;
    default: return JSON.stringify(e);
  }
}

function addEvent(e) {
  const div = document.createElement('div');
  div.className = 'event ' + e.type;
  const t = new Date(e.ts * 1000).toLocaleTimeString();
  div.innerHTML = '<span class="time">' + t + '</span> <span class="label">' +
    (labels[e.type] || e.type) + '</span><div class="body">' +
    formatBody(e).replace(/</g,'&lt;') + '</div>';
  log.appendChild(div);
  div.scrollIntoView({behavior: 'smooth'});
}

const es = new EventSource('/api/events');
es.onopen = () => { dot.style.background = '#9ece6a'; status.textContent = 'connected'; };
es.onmessage = (msg) => { addEvent(JSON.parse(msg.data)); };
es.onerror = () => { dot.style.background = '#f7768e'; status.textContent = 'disconnected'; };
</script>
</body></html>"""


def main():
    """Entry point for eddie-agent command."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logger.info("Starting Eddie Agent on port %d (model: %s)", config.agent_port, config.ollama_model)
    app.run(host="0.0.0.0", port=config.agent_port, debug=False)


if __name__ == "__main__":
    main()
