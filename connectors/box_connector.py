"""Box connector for the agentic harness.

A thin, dependency-light client over the Box REST API (v2.0). Used by the
Box-backed skills (document summarizer, notes-assignments, ticket lookup).

Authentication (checked in this order):
  1. BOX_API_TOKEN                      -> used directly as a bearer token
  2. Client Credentials Grant (CCG):    -> exchanged for a token at runtime
       BOX_CLIENT_ID, BOX_CLIENT_SECRET,
       and one of:
         BOX_ENTERPRISE_ID  (box_subject_type=enterprise)
         BOX_USER_ID        (box_subject_type=user)

If no credentials are configured, every call raises ``BoxAuthError`` with a
clear message — the skills surface that to the user rather than inventing data.

CLI (handy for testing the connector in isolation):
    python connectors/box_connector.py whoami
    python connectors/box_connector.py search "<keywords>"
    python connectors/box_connector.py find-folder "<folder name>"
    python connectors/box_connector.py list <folder_id>
    python connectors/box_connector.py text <file_id>
    python connectors/box_connector.py details <file_id>
"""

from __future__ import annotations

import json
import os
import sys
import time

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

API = "https://api.box.com/2.0"
TOKEN_URL = "https://api.box.com/oauth2/token"
_TIMEOUT = 30


class BoxAuthError(RuntimeError):
    """Raised when no usable Box credentials are configured."""


class BoxError(RuntimeError):
    """Raised on a non-2xx Box API response."""


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
_cached_token: str | None = None


def _ccg_token() -> str:
    client_id = os.getenv("BOX_CLIENT_ID")
    client_secret = os.getenv("BOX_CLIENT_SECRET")
    enterprise_id = os.getenv("BOX_ENTERPRISE_ID")
    user_id = os.getenv("BOX_USER_ID")
    if not (client_id and client_secret and (enterprise_id or user_id)):
        raise BoxAuthError(
            "No Box credentials. Set BOX_API_TOKEN, or BOX_CLIENT_ID + "
            "BOX_CLIENT_SECRET + (BOX_ENTERPRISE_ID or BOX_USER_ID) for CCG."
        )
    if enterprise_id:
        subject_type, subject_id = "enterprise", enterprise_id
    else:
        subject_type, subject_id = "user", user_id
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "box_subject_type": subject_type,
            "box_subject_id": subject_id,
        },
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        raise BoxAuthError(f"Box CCG token request failed: {resp.status_code} {resp.text}")
    return resp.json()["access_token"]


def _token() -> str:
    global _cached_token
    if _cached_token:
        return _cached_token
    direct = os.getenv("BOX_API_TOKEN")
    _cached_token = direct.strip() if direct else _ccg_token()
    return _cached_token


def _headers(extra: dict | None = None) -> dict:
    h = {"Authorization": f"Bearer {_token()}"}
    if extra:
        h.update(extra)
    return h


def _get(path: str, *, params: dict | None = None, headers: dict | None = None):
    resp = requests.get(
        f"{API}{path}", params=params, headers=_headers(headers), timeout=_TIMEOUT
    )
    if resp.status_code == 401:
        raise BoxAuthError("Box returned 401 — token missing, expired, or unauthorized.")
    if not resp.ok:
        raise BoxError(f"GET {path} -> {resp.status_code}: {resp.text[:300]}")
    return resp


# --------------------------------------------------------------------------- #
# Search / browse
# --------------------------------------------------------------------------- #
def search_files(query: str, *, limit: int = 10, file_only: bool = True) -> list[dict]:
    """Keyword search across Box. Returns lightweight item dicts."""
    params = {"query": query, "limit": limit}
    if file_only:
        params["type"] = "file"
    entries = _get("/search", params=params).json().get("entries", [])
    return [
        {
            "id": e.get("id"),
            "name": e.get("name"),
            "type": e.get("type"),
            "parent": (e.get("parent") or {}).get("name"),
        }
        for e in entries
    ]


def find_folder(name: str) -> list[dict]:
    """Search Box for a folder by name."""
    entries = _get(
        "/search", params={"query": name, "type": "folder", "limit": 10}
    ).json().get("entries", [])
    return [{"id": e.get("id"), "name": e.get("name")} for e in entries]


def list_folder(folder_id: str = "0") -> list[dict]:
    """List the items in a folder ('0' is the Box root)."""
    entries = _get(
        f"/folders/{folder_id}/items",
        params={"fields": "id,name,type", "limit": 200},
    ).json().get("entries", [])
    return [
        {"id": e.get("id"), "name": e.get("name"), "type": e.get("type")} for e in entries
    ]


def walk_files(root_id: str = "0", *, max_files: int = 50, max_depth: int = 3) -> list[dict]:
    """Breadth-first walk of folders, returning files (bounded for safety).

    Useful when Box content-search misses a term (e.g. text inside Box notes that
    is not indexed) and a skill needs to scan file text directly.
    """
    out: list[dict] = []
    queue: list[tuple[str, int]] = [(root_id, 0)]
    seen: set[str] = set()
    while queue and len(out) < max_files:
        folder_id, depth = queue.pop(0)
        if folder_id in seen:
            continue
        seen.add(folder_id)
        for item in list_folder(folder_id):
            if item.get("type") == "file":
                out.append(item)
                if len(out) >= max_files:
                    break
            elif item.get("type") == "folder" and depth < max_depth:
                queue.append((item["id"], depth + 1))
    return out[:max_files]


# --------------------------------------------------------------------------- #
# File details / metadata / text
# --------------------------------------------------------------------------- #
def get_file_info(file_id: str) -> dict:
    fields = "id,name,description,size,created_at,modified_at,created_by,owned_by,parent"
    return _get(f"/files/{file_id}", params={"fields": fields}).json()


def get_all_metadata(file_id: str) -> dict:
    """Return every metadata instance attached to a file (templates + global)."""
    try:
        entries = _get(f"/files/{file_id}/metadata").json().get("entries", [])
    except BoxError:
        return {}
    out = {}
    for inst in entries:
        scope = inst.get("$scope", "global")
        template = inst.get("$template", "properties")
        out[f"{scope}/{template}"] = {
            k: v for k, v in inst.items() if not k.startswith("$")
        }
    return out


def get_file_text(file_id: str, *, max_chars: int = 200_000) -> str:
    """Extract a file's text via Box 'extracted_text' representations.

    Falls back to the raw /content endpoint for already-plain-text files.
    Returns '' if Box has no text representation (e.g. a scanned image).
    """
    info = _get(
        f"/files/{file_id}",
        params={"fields": "representations"},
        headers={"X-Rep-Hints": "[extracted_text]"},
    ).json()
    reps = (info.get("representations") or {}).get("entries", [])
    text_rep = next(
        (r for r in reps if r.get("representation") == "extracted_text"), None
    )
    if text_rep:
        url_tmpl = (text_rep.get("content") or {}).get("url_template")
        info_url = (text_rep.get("info") or {}).get("url")
        # Representation may need to be generated; poll its status briefly.
        for _ in range(10):
            status = (text_rep.get("status") or {}).get("state")
            if status == "success" or status is None:
                break
            if info_url:
                resp = requests.get(info_url, headers=_headers(), timeout=_TIMEOUT)
                if resp.ok:
                    text_rep = resp.json()
            time.sleep(1)
        if url_tmpl:
            content_url = url_tmpl.replace("{+asset_path}", "")
            resp = requests.get(content_url, headers=_headers(), timeout=_TIMEOUT)
            if resp.ok:
                return resp.text[:max_chars]
    # Fallback: download raw content (works for .txt, .md, Box notes, etc.)
    resp = requests.get(
        f"{API}/files/{file_id}/content", headers=_headers(), timeout=_TIMEOUT
    )
    if resp.ok and resp.text:
        return resp.text[:max_chars]
    return ""


def who_am_i() -> dict:
    return _get("/users/me", params={"fields": "id,name,login"}).json()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    cmd, *rest = argv
    try:
        if cmd == "whoami":
            print(json.dumps(who_am_i(), indent=2))
        elif cmd == "search":
            print(json.dumps(search_files(" ".join(rest)), indent=2))
        elif cmd == "find-folder":
            print(json.dumps(find_folder(" ".join(rest)), indent=2))
        elif cmd == "list":
            print(json.dumps(list_folder(rest[0] if rest else "0"), indent=2))
        elif cmd == "text":
            print(get_file_text(rest[0]))
        elif cmd == "details":
            print(
                json.dumps(
                    {"info": get_file_info(rest[0]), "metadata": get_all_metadata(rest[0])},
                    indent=2,
                )
            )
        else:
            print(f"Unknown command: {cmd}")
            print(__doc__)
            return 1
    except BoxAuthError as e:
        print(f"AUTH ERROR: {e}", file=sys.stderr)
        return 2
    except BoxError as e:
        print(f"BOX ERROR: {e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
