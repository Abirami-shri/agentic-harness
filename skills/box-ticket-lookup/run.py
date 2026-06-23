"""get_ticket_details — look up a ticket by ID via the Box connector.

Searches Box for the ticket ID (matched in file name / content / metadata), then
returns the best match's file info, all metadata instances, and a content excerpt.
Deterministic data retrieval — the agent formats the result for the user.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from connectors import box_connector as box  # noqa: E402

_EXCERPT_CHARS = 1200
_CONTEXT_LINES = 2
_WINDOW_CHARS = 280  # focused char window around a mention on a long/unbroken line


def _best_match(ticket_id: str, matches: list[dict]) -> dict:
    """Prefer a file whose name contains the ticket ID verbatim."""
    tid = ticket_id.lower()
    for m in matches:
        if tid in (m.get("name") or "").lower():
            return m
    return matches[0]


def _scan_mentions(ticket_id: str) -> list[dict]:
    """Fallback when search finds no ticket file: scan file text for the ID.

    Box content-search does not always index note text, yet tickets are often
    only *mentioned* inside notes/docs. This walks the user's files, fetches their
    text, and returns the lines mentioning the ticket ID with surrounding context.
    """
    tid = ticket_id.lower()
    mentions = []
    for f in box.walk_files(max_files=40):
        text = box.get_file_text(f["id"])
        if tid not in text.lower():
            continue
        lines = text.splitlines()
        excerpts = []
        for i, line in enumerate(lines):
            if tid not in line.lower():
                continue
            if len(line) > 2 * _WINDOW_CHARS:
                # Long/unbroken line (e.g. a Box note): window around each hit.
                low = line.lower()
                start = 0
                while (pos := low.find(tid, start)) != -1:
                    lo = max(0, pos - _WINDOW_CHARS)
                    hi = min(len(line), pos + len(tid) + _WINDOW_CHARS)
                    prefix = "…" if lo > 0 else ""
                    suffix = "…" if hi < len(line) else ""
                    excerpts.append(f"{prefix}{line[lo:hi].strip()}{suffix}")
                    start = pos + len(tid)
            else:
                lo = max(0, i - _CONTEXT_LINES)
                hi = min(len(lines), i + _CONTEXT_LINES + 1)
                excerpts.append("\n".join(lines[lo:hi]).strip())
        mentions.append(
            {"source_id": f["id"], "source_name": f.get("name"), "excerpts": excerpts}
        )
    return mentions


def run(args: dict) -> str:
    ticket_id = (args.get("ticket_id") or "").strip()
    if not ticket_id:
        return json.dumps({"ok": False, "error": "ticket_id is required."})
    try:
        matches = box.search_files(ticket_id, limit=10)
        if not matches:
            # No ticket file by that name/metadata — scan note/doc text for mentions.
            mentions = _scan_mentions(ticket_id)
            if mentions:
                return json.dumps(
                    {
                        "ok": True,
                        "found": True,
                        "source": "content_mention",
                        "ticket_id": ticket_id,
                        "mentions": mentions,
                    }
                )
            return json.dumps(
                {"ok": True, "found": False, "ticket_id": ticket_id, "matches": []}
            )
        best = _best_match(ticket_id, matches)
        info = box.get_file_info(best["id"])
        metadata = box.get_all_metadata(best["id"])
        excerpt = box.get_file_text(best["id"], max_chars=_EXCERPT_CHARS)
        return json.dumps(
            {
                "ok": True,
                "found": True,
                "ticket_id": ticket_id,
                "matches": matches,
                "details": {
                    "id": info.get("id"),
                    "name": info.get("name"),
                    "description": info.get("description"),
                    "owned_by": (info.get("owned_by") or {}).get("name"),
                    "created_by": (info.get("created_by") or {}).get("name"),
                    "modified_at": info.get("modified_at"),
                    "metadata": metadata,
                    "excerpt": excerpt,
                },
            }
        )
    except box.BoxAuthError as e:
        return json.dumps({"ok": False, "error": f"Box auth: {e}"})
    except box.BoxError as e:
        return json.dumps({"ok": False, "error": f"Box API: {e}"})


if __name__ == "__main__":
    print(run({"ticket_id": " ".join(sys.argv[1:])}))
