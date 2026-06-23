---
name: summarize_document
description: Fetch a document or notes from Box and summarize it into a structured digest of key points, decisions, and action items.
---

# Document Summarizer (Box)

Call `summarize_document` with the file the user named (ID, exact name, or
keywords). The tool returns the document's real text from Box. Summarize **only**
that returned text — never invent content.

If the tool returns `ok: false` (file not found, no text representation, or no Box
credentials), tell the user exactly that and stop. Do not fabricate a summary.

Produce a tight digest (well under 20% of the source length) with all three
sections — write "None identified" rather than omitting one:

```
## Key Points
- the substantive topics, most important first

## Decisions
- anything explicitly resolved or agreed

## Action Items
- [ ] Owner — Task — (due date if mentioned; "Unassigned" if no owner stated)
```

For non-meeting documents (design docs, reports), adapt the framing naturally —
"Decisions" may become "Conclusions/Recommendations" — but keep the three-part shape.
