---
name: get_ticket_details
description: Retrieve the details of a ticket by its ticket ID from Box (file name, content, or metadata).
---

# Ticket Lookup (Box)

Call `get_ticket_details` with the `ticket_id` the user gave. The tool searches
Box and returns the matching item's real details — name, owner, any metadata
fields (status, assignee, priority, etc.), and a short content excerpt.

The tool returns one of two `found: true` shapes:

1. **A ticket file** (`details`): a Box file matched the ID directly. Present it:
   - Lead with the ticket ID and its title/file name.
   - Surface key metadata fields (status, assignee/owner, priority, dates) if present.
   - Give a one-or-two-line summary from the `excerpt`.

2. **Content mentions** (`source: "content_mention"`, `mentions`): no ticket file
   exists, but the ID is referenced inside notes/docs. For each mention, read the
   `excerpts` and summarize what they say about the ticket — its status, who owns
   it, and any next step — and cite the `source_name` it came from.

Behaviour rules:

- If `found` is false, say "No ticket found in Box for <ticket_id>" and stop.
- If there are multiple `matches`, note them and report the best (first) match,
  offering to look at the others.
- Never invent field values or status that aren't in the tool output.
