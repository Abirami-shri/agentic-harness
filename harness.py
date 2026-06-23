"""Agentic harness: run the deployed Foundry agent and execute its tool calls.

The agent's reasoning runs in Azure AI Foundry. This harness is the client-side
runtime: it opens a thread, sends the user's message, starts a run, and whenever
the run *requires action* it executes the requested skill locally (via
skill_runtime) and submits the output back to Foundry — looping until the agent
produces its final answer.

Usage:
  python harness.py "summarize DIS-Switch Port Config.pdf from Box"
  python harness.py "who is assigned what in my standup notes?"
  python harness.py "get details for ticket DIS-1423"
  python harness.py            # interactive REPL

Requires the agent to have been deployed first (see deploy_foundry.py); the agent
id is read from .foundry_agent.json, or one is created on the fly if absent.
"""

from __future__ import annotations

import json
import sys
import time

import agent_def
import deploy_foundry
import skill_runtime

_POLL_SECONDS = 1.0
_RUN_TIMEOUT_SECONDS = 180


def _ensure_agent_id() -> str:
    state = deploy_foundry._load_state()
    if state.get("agent_id"):
        return state["agent_id"]
    print("No deployed agent found — deploying now...", file=sys.stderr)
    return deploy_foundry.deploy()


def _handle_required_action(client, thread_id: str, run) -> None:
    """Execute every requested tool call locally and submit the outputs."""
    calls = run.required_action.submit_tool_outputs.tool_calls
    outputs = []
    for call in calls:
        name = call.function.name
        try:
            args = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        print(f"  ↳ tool: {name}({args})", file=sys.stderr)
        result = skill_runtime.dispatch(name, args)
        outputs.append({"tool_call_id": call.id, "output": result})
    client.runs.submit_tool_outputs(
        thread_id=thread_id, run_id=run.id, tool_outputs=outputs
    )


def _last_agent_text(client, thread_id: str) -> str:
    from azure.ai.agents.models import MessageRole

    msg = client.messages.get_last_message_text_by_role(thread_id, MessageRole.AGENT)
    if msg is not None and getattr(msg, "text", None) is not None:
        return msg.text.value
    return "(no assistant message produced)"


def ask(client, agent_id: str, thread_id: str, user_message: str) -> str:
    client.messages.create(thread_id=thread_id, role="user", content=user_message)
    run = client.runs.create(thread_id=thread_id, agent_id=agent_id)
    deadline = time.time() + _RUN_TIMEOUT_SECONDS
    while True:
        run = client.runs.get(thread_id=thread_id, run_id=run.id)
        status = run.status
        if status == "requires_action":
            _handle_required_action(client, thread_id, run)
        elif status == "completed":
            return _last_agent_text(client, thread_id)
        elif status in ("failed", "cancelled", "expired"):
            return f"Run {status}: {getattr(run, 'last_error', None)}"
        if time.time() > deadline:
            return "Run timed out."
        time.sleep(_POLL_SECONDS)


def main(argv: list[str]) -> int:
    client = deploy_foundry._agents_client()
    agent_id = _ensure_agent_id()
    thread = client.threads.create()

    if argv:
        print(ask(client, agent_id, thread.id, " ".join(argv)))
        return 0

    print(f"Box Skills Agent ({agent_def.AGENT_NAME}). Ctrl-D to exit.")
    while True:
        try:
            line = input("you> ").strip()
        except EOFError:
            print()
            return 0
        if line:
            print(ask(client, agent_id, thread.id, line))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
