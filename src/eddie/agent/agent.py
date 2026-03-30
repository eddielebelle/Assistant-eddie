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


def _stream_ollama(model: str, messages: list, tools: list):
    """Stream an Ollama chat call, collecting the full response.

    Returns (content, tool_calls) once the stream ends.
    Emits llm_token events for each chunk so the monitor updates live.
    """
    content_parts = []
    tool_calls = []

    for chunk in ollama.chat(model=model, messages=messages, tools=tools, stream=True):
        msg = chunk.message
        # Accumulate text tokens
        if msg.content:
            content_parts.append(msg.content)
            events.emit("llm_token", {"token": msg.content})
        # Tool calls arrive in the final chunk(s)
        if msg.tool_calls:
            tool_calls.extend(msg.tool_calls)

    return "".join(content_parts), tool_calls


def chat(user_text: str, agent_name: str = "EDDIE_VOICE") -> str:
    """Process a user message through the streaming tool-calling agent loop.

    This is the core loop - same pattern as kindrent's Ray:
    1. Send user message + tools to LLM (streaming)
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

    # Streaming Ollama tool-calling loop
    events.emit("llm_start", {"model": model})
    content, tool_calls = _stream_ollama(model, messages, tools)

    # Loop while the model wants to call tools
    while tool_calls:
        # Add the assistant's tool-call message to history
        assistant_msg = {"role": "assistant", "content": content, "tool_calls": [
            {"function": {"name": tc.function.name, "arguments": tc.function.arguments or {}}}
            for tc in tool_calls
        ]}
        conversation.add_raw(assistant_msg)

        for tool_call in tool_calls:
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
        content, tool_calls = _stream_ollama(model, messages, tools)

    # Final text response from the model
    conversation.add_message("assistant", content)
    events.emit("response", {"text": content})

    logger.info("Eddie response: %s", content[:200])
    return content


def chat_stream(user_text: str, agent_name: str = "EDDIE_VOICE"):
    """Streaming version of chat - yields tokens as they arrive from the LLM.

    Yields NDJSON: {"token": "..."} per chunk, {"done": true, "response": "..."} at end.
    Tool-call rounds are resolved internally (LLM typically emits no text during those).
    The final text response is streamed token-by-token to the client.
    """
    import json

    agent_config = AGENT_CONFIGS[agent_name]
    model = config.ollama_model or agent_config.get("model", "qwen2.5:14b")
    tools = agent_config["tools"]

    conversation.add_message("user", user_text)
    events.emit("user_input", {"text": user_text})

    system_prompt = _build_system_prompt(agent_config)
    messages = conversation.get_messages(system_prompt)

    while True:
        events.emit("llm_start", {"model": model})
        content_parts = []
        tool_calls = []

        for chunk in ollama.chat(model=model, messages=messages, tools=tools, stream=True):
            msg = chunk.message
            if msg.content:
                content_parts.append(msg.content)
                events.emit("llm_token", {"token": msg.content})
                yield json.dumps({"token": msg.content}) + "\n"
            if msg.tool_calls:
                tool_calls.extend(msg.tool_calls)

        content = "".join(content_parts)

        if not tool_calls:
            break

        # Tool-call round — handle internally, loop back to LLM
        assistant_msg = {"role": "assistant", "content": content, "tool_calls": [
            {"function": {"name": tc.function.name, "arguments": tc.function.arguments or {}}}
            for tc in tool_calls
        ]}
        conversation.add_raw(assistant_msg)

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = tool_call.function.arguments or {}
            logger.info("LLM requested tool: %s(%s)", tool_name, arguments)
            events.emit("tool_call", {"tool": tool_name, "args": arguments})
            result = execute_tool(tool_name, arguments)
            events.emit("tool_result", {"tool": tool_name, "result": result[:500]})
            conversation.add_raw({"role": "tool", "content": result})

        messages = conversation.get_messages(system_prompt)

    conversation.add_message("assistant", content)
    events.emit("response", {"text": content})
    logger.info("Eddie response: %s", content[:200])
    yield json.dumps({"done": True, "response": content}) + "\n"


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """HTTP endpoint for the agent service. Supports streaming via Accept header."""
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "Missing 'text' field"}), 400

    user_text = data["text"]
    agent_name = data.get("agent", "EDDIE_VOICE")
    stream = data.get("stream", False)

    try:
        if stream:
            return Response(chat_stream(user_text, agent_name), mimetype="application/x-ndjson")
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
  llm_token:  'TOKEN',
  tool_call:  'TOOL',
  tool_result:'RESULT',
  response:   'OUTPUT'
};

let streamDiv = null;  // tracks the active streaming element

function formatBody(e) {
  switch(e.type) {
    case 'user_input': return e.text;
    case 'llm_start':  return 'Processing with ' + e.model + '...';
    case 'tool_call':  return e.tool + '(' + JSON.stringify(e.args) + ')';
    case 'tool_result':return e.tool + ' \u2192 ' + e.result;
    case 'response':   return e.text;
    default: return JSON.stringify(e);
  }
}

function addEvent(e) {
  // Stream tokens into a single element
  if (e.type === 'llm_token') {
    if (!streamDiv) {
      streamDiv = document.createElement('div');
      streamDiv.className = 'event llm_start';
      const t = new Date(e.ts * 1000).toLocaleTimeString();
      streamDiv.innerHTML = '<span class="time">' + t + '</span> <span class="label">STREAM</span><div class="body"></div>';
      log.appendChild(streamDiv);
    }
    const body = streamDiv.querySelector('.body');
    body.textContent += e.token;
    streamDiv.scrollIntoView({behavior: 'smooth'});
    return;
  }

  // Final response closes the stream
  if (e.type === 'response') {
    if (streamDiv) {
      streamDiv.className = 'event response';
      streamDiv.querySelector('.label').textContent = 'OUTPUT';
      streamDiv = null;
    }
    return;
  }

  // New LLM start closes any previous stream
  if (e.type === 'llm_start') { streamDiv = null; }

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
