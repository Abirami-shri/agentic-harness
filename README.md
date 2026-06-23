# agentic-harness

A skills + agentic harness that deploys to **Azure AI Foundry**. One agent, whose
reasoning runs in the Foundry Agent Service, backed by three Box-powered skills.

## What's here

```
agentic-harness/
├─ agent_def.py          # agent name, instructions (base + each SKILL.md), tool schemas
├─ deploy_foundry.py     # create/update the agent in your Foundry project
├─ harness.py            # runtime: thread → run → execute tool calls → final answer
├─ skill_runtime.py      # discover skills, expose tool schemas, dispatch tool calls
├─ connectors/
│  └─ box_connector.py   # Box REST client (auth, search, browse, text, metadata)
└─ skills/
   ├─ document-summarizer/   # summarize_document
   ├─ notes-assignments/     # list_notes_assignments
   └─ box-ticket-lookup/     # get_ticket_details
```

Each skill is a folder with `tool.json` (the function-tool schema Foundry calls),
`SKILL.md` (instructions folded into the agent), and `run.py` (`run(args) -> str`).

## The three skills

| Skill / tool | What it does |
|---|---|
| **summarize_document** | Fetches a Box document's text and summarizes it into Key Points / Decisions / Action Items. |
| **list_notes_assignments** | Fetches notes from Box and extracts the action items assigned to each person (optionally filtered to one person). |
| **get_ticket_details** | Looks up a ticket by ID in Box (name/content/metadata) and returns its details. |

## How it works

The **agent reasoning runs inside Azure AI Foundry** (gpt-4o). Foundry decides
which skill to call; this harness executes that skill locally (the skills are
*function tools*, executed client-side) and submits the result back. The skills
are deterministic Box operations — no LLM is called from this repo.

```
user → harness.py → Foundry agent (picks a tool)
                       ├─ summarize_document   → Box: fetch text
                       ├─ list_notes_assignments → Box: fetch notes
                       └─ get_ticket_details     → Box: search + metadata
                     ← Foundry composes the final answer
```

## Setup

```bash
cd agentic-harness
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in Box + Foundry values
```

Auth for Foundry: either `az login` (Entra, recommended) or set
`AZURE_AI_PROJECT_API_KEY`. Box: set `BOX_API_TOKEN` (or the CCG variables).

## Deploy the agent to Foundry

```bash
python deploy_foundry.py --show     # preview instructions + tools (no deploy)
python deploy_foundry.py            # create/update the agent; writes .foundry_agent.json
```

## Run the harness

```bash
python harness.py "summarize 'DIS-Switch Port Config.pdf' from Box"
python harness.py "who is assigned what in my standup notes?"
python harness.py "get details for ticket DIS-1423"
python harness.py                   # interactive REPL
```

## Test a skill / the connector in isolation (no Foundry needed)

```bash
python skill_runtime.py                       # list discovered tool schemas
python connectors/box_connector.py whoami     # verify Box auth
python skills/box-ticket-lookup/run.py DIS-1423
```

## Hosting the tool executor (optional)

`harness.py` runs the client-side tool loop. To host it instead of running from a
laptop, build the container and deploy it (e.g. Azure Container Apps):

```bash
docker build -t agentic-harness .
```
