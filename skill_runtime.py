"""Skill runtime: discover skills, expose their tool schemas, and dispatch calls.

A *skill* is a directory under ``skills/`` containing:

  * ``tool.json``  — the function-tool schema registered with the Foundry agent:
        {"name", "description", "parameters" (JSON Schema)}
  * ``SKILL.md``   — instructions for the agent on how/when to use the skill
                     (folded into the agent's system instructions by agent_def.py)
  * ``run.py``     — implements ``run(args: dict) -> str`` (the tool output)

The Foundry agent decides *which* skill to call (that reasoning runs in Foundry).
This runtime only (a) advertises the schemas at deploy time and (b) executes the
chosen skill when a run requires action.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILLS_DIR = ROOT / "skills"

# Make ``from connectors import box_connector`` work for every skill's run.py.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class Skill:
    def __init__(self, path: Path):
        self.path = path
        self.schema = json.loads((path / "tool.json").read_text())
        self.name = self.schema["name"]
        skill_md = path / "SKILL.md"
        self.instructions = skill_md.read_text() if skill_md.exists() else ""
        self._run = None

    def _load_run(self):
        if self._run is None:
            spec = importlib.util.spec_from_file_location(
                f"skill_{self.name}", self.path / "run.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if not hasattr(module, "run"):
                raise AttributeError(f"Skill '{self.name}' run.py has no run(args) function")
            self._run = module.run
        return self._run

    def execute(self, args: dict) -> str:
        try:
            return self._load_run()(args or {})
        except Exception as e:  # surface errors as tool output, never crash the run
            return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})


def load_skills() -> dict[str, Skill]:
    if not SKILLS_DIR.exists():
        return {}
    skills: dict[str, Skill] = {}
    for d in sorted(SKILLS_DIR.iterdir()):
        if d.is_dir() and (d / "tool.json").exists():
            s = Skill(d)
            skills[s.name] = s
    return skills


def tool_schemas() -> list[dict]:
    return [s.schema for s in load_skills().values()]


def dispatch(name: str, args: dict) -> str:
    skills = load_skills()
    if name not in skills:
        return json.dumps({"ok": False, "error": f"Unknown skill/tool: {name}"})
    return skills[name].execute(args)


if __name__ == "__main__":
    # Quick introspection: list discovered skills and their schemas.
    print(json.dumps(tool_schemas(), indent=2))
