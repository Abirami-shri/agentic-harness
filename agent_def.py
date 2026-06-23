"""Definition of the Foundry agent: name, instructions, and tool schemas.

The agent's *reasoning* runs inside the Azure AI Foundry Agent Service. This file
assembles what that hosted agent needs:

  * a system ``instructions`` block (a base policy + each skill's SKILL.md), and
  * the function-tool schemas the agent may call (from skill_runtime).

Both deploy_foundry.py (registration) and harness.py (runtime) import from here so
the deployed agent and the local executor stay in sync.
"""

from __future__ import annotations

import os

import skill_runtime

AGENT_NAME = os.getenv("FOUNDRY_AGENT_NAME", "box-skills-agent")

_BASE_INSTRUCTIONS = """\
You are the Box Skills Agent. You help users work with documents, notes, and
tickets stored in Box by calling the tools available to you.

Operating rules:
- Always ground answers in tool output. Never invent file contents, assignments,
  or ticket fields that a tool did not return.
- Pick the right tool for the request:
    * summarize / recap / digest a Box document or notes  -> summarize_document
    * who is assigned what / action items from notes       -> list_notes_assignments
    * details for a specific ticket ID                      -> get_ticket_details
- If a tool returns ok:false (not found, no text, or missing Box credentials),
  report that plainly to the user and stop — do not fabricate a result.
- Keep outputs tight and skimmable. Use the formatting each skill describes below.

The behaviour for each tool follows.
"""


def build_instructions() -> str:
    parts = [_BASE_INSTRUCTIONS]
    for skill in skill_runtime.load_skills().values():
        if skill.instructions:
            parts.append(f"\n\n--- SKILL: {skill.name} ---\n{skill.instructions}")
    return "".join(parts)


def function_tools() -> list[dict]:
    """OpenAI/Foundry function-tool definitions for every discovered skill."""
    return [
        {"type": "function", "function": schema}
        for schema in skill_runtime.tool_schemas()
    ]


if __name__ == "__main__":
    print(f"# Agent: {AGENT_NAME}\n")
    print(build_instructions())
    print("\n# Tools:")
    for t in function_tools():
        print(f"  - {t['function']['name']}: {t['function']['description'][:80]}...")
