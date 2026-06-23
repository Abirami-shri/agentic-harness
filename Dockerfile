# Runtime image for the agentic harness (client-side tool executor for the
# Foundry agent). Build & push this when you want the tool-execution loop hosted
# (e.g. as an Azure Container App) rather than run from a laptop.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: run the harness REPL. Override CMD to pass a one-shot prompt, or to run
# `python deploy_foundry.py` to (re)register the agent.
ENTRYPOINT ["python", "harness.py"]
