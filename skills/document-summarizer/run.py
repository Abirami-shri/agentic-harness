"""summarize_document — fetch a document's text from Box for the agent to digest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from connectors import box_connector as box  # noqa: E402


def _resolve_file(ref: str) -> dict | None:
    ref = (ref or "").strip()
    if not ref:
        return None
    if ref.isdigit():  # already a Box file ID
        try:
            info = box.get_file_info(ref)
            return {"id": info["id"], "name": info.get("name")}
        except box.BoxError:
            return None
    matches = box.search_files(ref, limit=5)
    return matches[0] if matches else None


def run(args: dict) -> str:
    ref = args.get("file", "")
    try:
        match = _resolve_file(ref)
        if not match:
            return json.dumps({"ok": False, "error": f"Not found in Box: {ref!r}"})
        text = box.get_file_text(match["id"])
        if not text.strip():
            return json.dumps(
                {
                    "ok": False,
                    "error": f"No text representation available for {match.get('name')!r} "
                    "(e.g. a scanned image).",
                }
            )
        return json.dumps(
            {
                "ok": True,
                "file_id": match["id"],
                "name": match.get("name"),
                "char_count": len(text),
                "text": text,
            }
        )
    except box.BoxAuthError as e:
        return json.dumps({"ok": False, "error": f"Box auth: {e}"})
    except box.BoxError as e:
        return json.dumps({"ok": False, "error": f"Box API: {e}"})


if __name__ == "__main__":
    print(run({"file": " ".join(sys.argv[1:])}))
