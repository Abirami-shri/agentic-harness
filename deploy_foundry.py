"""Deploy (create or update) the agent in your provisioned Azure AI Foundry project.

This registers the agent — its instructions and its three function tools — with the
Foundry Agent Service. The model's reasoning runs in Foundry; the function tools
are executed client-side by harness.py at run time.

Prerequisites:
  * The Foundry project is already provisioned (it is).
  * Auth: `az login` (DefaultAzureCredential) OR set AZURE_AI_PROJECT_API_KEY.
  * Env (see .env / .env.example):
      AZURE_AI_PROJECT_ENDPOINT   (falls back to AZURE_FOUNDRY_ENDPOINT)
      AZURE_OPENAI_DEPLOYMENT     model deployment name for the agent (e.g. gpt-4o)

Usage:
  python deploy_foundry.py            # create or update the agent
  python deploy_foundry.py --show     # print resolved instructions/tools, don't deploy

On success the agent id is written to .foundry_agent.json so harness.py can reuse it.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

import agent_def

STATE_FILE = Path(__file__).resolve().parent / ".foundry_agent.json"


def _endpoint() -> str:
    ep = os.getenv("AZURE_AI_PROJECT_ENDPOINT") or os.getenv("AZURE_FOUNDRY_ENDPOINT")
    if not ep:
        sys.exit(
            "Missing project endpoint. Set AZURE_AI_PROJECT_ENDPOINT (or "
            "AZURE_FOUNDRY_ENDPOINT) to your Foundry project URL, e.g. "
            "https://<resource>.services.ai.azure.com/api/projects/<project>"
        )
    return ep.rstrip("/")


def _credential():
    """Prefer an API key if provided, else fall back to Entra (az login)."""
    api_key = os.getenv("AZURE_AI_PROJECT_API_KEY") or os.getenv("AZURE_FOUNDRY_API_KEY")
    if api_key:
        from azure.core.credentials import AzureKeyCredential

        return AzureKeyCredential(api_key)
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


def _agents_client():
    """The Foundry Agent Service data-plane client (azure-ai-agents GA)."""
    from azure.ai.agents import AgentsClient

    return AgentsClient(endpoint=_endpoint(), credential=_credential())


def _load_state() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def deploy() -> str:
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    instructions = agent_def.build_instructions()
    tools = agent_def.function_tools()

    client = _agents_client()
    state = _load_state()
    existing_id = state.get("agent_id")

    if existing_id:
        agent = client.update_agent(
            agent_id=existing_id,
            model=model,
            name=agent_def.AGENT_NAME,
            instructions=instructions,
            tools=tools,
        )
        action = "Updated"
    else:
        agent = client.create_agent(
            model=model,
            name=agent_def.AGENT_NAME,
            instructions=instructions,
            tools=tools,
        )
        action = "Created"

    agent_id = getattr(agent, "id", None) or agent["id"]
    STATE_FILE.write_text(
        json.dumps({"agent_id": agent_id, "name": agent_def.AGENT_NAME, "model": model}, indent=2)
    )
    print(f"{action} agent '{agent_def.AGENT_NAME}' ({agent_id}) on model '{model}'.")
    print(f"  Tools: {', '.join(t['function']['name'] for t in tools)}")
    print(f"  State saved to {STATE_FILE.name}")
    return agent_id


def show() -> None:
    print(f"Agent name : {agent_def.AGENT_NAME}")
    print(f"Model      : {os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')}")
    print(f"Endpoint   : {os.getenv('AZURE_AI_PROJECT_ENDPOINT') or os.getenv('AZURE_FOUNDRY_ENDPOINT')}")
    print("\nTools:")
    for t in agent_def.function_tools():
        print(f"  - {t['function']['name']}")
    print("\n--- Instructions ---\n")
    print(agent_def.build_instructions())


if __name__ == "__main__":
    if "--show" in sys.argv:
        show()
    else:
        deploy()
