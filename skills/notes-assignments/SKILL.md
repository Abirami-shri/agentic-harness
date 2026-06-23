---
name: list_notes_assignments
description: Extract the list of action items / tasks assigned to people from notes stored in Box, optionally filtered to one person.
---

# Notes → Assignments

Call `list_notes_assignments` with the notes the user named (`notes`) and, if they
asked about a specific person, that name (`person`). The tool returns the real
notes text from Box (concatenating every file when a folder is matched).

Extract concrete **action items / assignments** from that text only — do not
invent tasks. For each item identify:

- **Owner** — the person the task is assigned to (use "Unassigned" if none stated)
- **Task** — what they need to do
- **Due date** — only if explicitly mentioned

Output a clean list grouped by owner:

```
### <Person>
- [ ] Task — (due date if mentioned)
```

If a `person` was provided, return only that person's items and say "No items
assigned to <person>" if there are none. If the tool returns `ok: false`, report
the error and stop — never fabricate assignments.
