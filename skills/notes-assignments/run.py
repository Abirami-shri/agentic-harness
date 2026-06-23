"""list_notes_assignments — fetch notes text from Box for assignment extraction.

Resolves the ``notes`` reference to one or more Box files (a single file by ID /
name / keyword, or every file inside a matched folder) and returns the combined
text. The agent extracts the per-person assignment list from it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from connectors import box_connector as box  # noqa: E402


def _gather_files(ref: str) -> list[dict]:
    ref = (ref or "").strip()
    if not ref:
        return []
    if ref.isdigit():
        try:
            info = box.get_file_info(ref)
            return [{"id": info["id"], "name": info.get("name")}]
        except box.BoxError:
            return []
    # Prefer file matches; fall back to treating the reference as a folder name.
    files = box.search_files(ref, limit=10)
    if files:
        return files
    folders = box.find_folder(ref)
    if folders:
        items = box.list_folder(folders[0]["id"])
        return [i for i in items if i.get("type") == "file"]
    return []


def run(args: dict) -> str:
    ref = args.get("notes", "")
    person = (args.get("person") or "").strip() or None
    try:
        files = _gather_files(ref)
        if not files:
            return json.dumps({"ok": False, "error": f"Not found in Box: {ref!r}"})
        chunks, sources = [], []
        for f in files:
            text = box.get_file_text(f["id"])
            if text.strip():
                chunks.append(f"### {f.get('name')} (id {f['id']})\n{text}")
                sources.append({"id": f["id"], "name": f.get("name")})
        if not chunks:
            return json.dumps(
                {"ok": False, "error": "No readable text in the matched Box file(s)."}
            )
        return json.dumps(
            {
                "ok": True,
                "person_filter": person,
                "sources": sources,
                "text": "\n\n".join(chunks),
            }
        )
    except box.BoxAuthError as e:
        return json.dumps({"ok": False, "error": f"Box auth: {e}"})
    except box.BoxError as e:
        return json.dumps({"ok": False, "error": f"Box API: {e}"})


if __name__ == "__main__":
    print(run({"notes": " ".join(sys.argv[1:])}))
