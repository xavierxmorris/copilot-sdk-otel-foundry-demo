# Copilot SDK → OpenTelemetry → Azure Monitor → Foundry Tracing & Evaluation

A small, runnable end-to-end demo that proves the loop:

> **GitHub Copilot SDK** (Python RAG agent over FSI dummy data) → **OTel traces** → **Azure Monitor / Application Insights** → **Azure AI Foundry Tracing tab** → **Foundry evaluation** runs against those traces (Groundedness / Relevance / Coherence).

The whole demo is designed to be talked through in ~10–15 minutes.

> ⚠️ **Disclaimer — dummy data.** The "Northwind Bank" knowledge base in [`data/`](data/) is entirely fictional. Interest rates, fees, policies, and figures are made up for demonstration purposes only. **Not financial advice. Not affiliated with any real institution.**

---

## What this demo shows

1. The Copilot SDK has built-in OpenTelemetry support — you configure it once with `TelemetryConfig` and it emits spans for **agent runs, LLM calls, and tool execution** following the [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/).
2. With `azure-monitor-opentelemetry`, those spans flow straight into **Application Insights** as `dependencies` / `requests` / `traces` rows.
3. Because the App Insights resource is **linked to an Azure AI Foundry project**, the Foundry **Tracing** tab renders the spans as an interactive tree — no second pipeline.
4. Foundry's **Evaluation** feature supports `Target = Traces`. It pulls real production interactions out of App Insights and scores them with built-in evaluators (Groundedness, Relevance, Coherence, …). Results are written back into App Insights as `customEvents` named `gen_ai.evaluation.result`.

**Net result:** observability becomes measurable quality.

## Architecture

```mermaid
flowchart LR
    A["Python app<br/>copilot-sdk[telemetry]"] -- "spawns" --> B["Copilot CLI<br/>(subprocess)"]
    B -- "OTLP HTTP :4318<br/>(agent · LLM · tool spans)" --> C["OTel Collector<br/>(docker-compose)"]
    C -- "azuremonitor exporter" --> D["Application Insights<br/>requests · dependencies<br/>traces · customEvents"]
    D -- "linked resource" --> E["Azure AI Foundry project<br/>Tracing tab"]
    E -- "Evaluation target = Traces<br/>Groundedness · Relevance · Coherence" --> D
    A -- "retrieve_docs tool" --> F["Azure AI Search<br/>northwind-kb index"]
    A -- "embeddings (seed_index.py)" --> G["Azure OpenAI<br/>gpt-5 / text-embedding-3-small"]
```

> Why a collector? The Copilot SDK CLI subprocess emits OTLP directly — it is not a Python in-proc exporter. The collector receives that OTLP traffic and ships it to App Insights via the `azuremonitor` contrib exporter. The same pattern is recommended in the official Copilot SDK observability docs.

## Prerequisites

- An Azure subscription with quota for `gpt-4o-mini` and `text-embedding-3-small` in `eastus2`
  (fallback: `swedencentral`).
- Azure AI Search **Basic** capacity in any region near you. The Bicep defaults the
  Search service to `westus3` because Basic capacity in `eastus2` is currently
  exhausted (and several other East-US regions are unreachable from some
  corporate VPN egress paths). Override with `azd env set SEARCH_LOCATION ...`
  before `azd up` if you want a different region.
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) (`azd`) ≥ 1.10.
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) (`az`) ≥ 2.60.
- Python ≥ 3.11.
- **Docker** (Desktop on Windows/macOS, engine on Linux) — used to run the OTel Collector.
- The **GitHub Copilot CLI** (`copilot`) installed on `PATH` and signed in.
  The Python SDK spawns it as a subprocess to make LLM calls and emit OTel spans.
- **Owner**, or **Contributor + User Access Administrator**, on the subscription
  (needed for the RBAC role assignments in [`infra/modules/rbac.bicep`](infra/modules/rbac.bicep)).

## Quickstart

```bash
# 1. Sign in and pick the right subscription
azd auth login
az login
az account set --subscription 51eb709f-8958-49c4-a547-ebdbd4bf66dc

# 2. Provision all Azure resources (App Insights is auto-linked to the Foundry
#    project as a Bicep `AppInsights` connection — no manual portal step).
azd env new copilot-otel-demo
azd env set AZURE_SUBSCRIPTION_ID 51eb709f-8958-49c4-a547-ebdbd4bf66dc
azd env set AZURE_LOCATION eastus2
# Optional: pick a different region for Azure AI Search if westus3 has no Basic capacity.
# azd env set SEARCH_LOCATION centralus
azd up

# 3. Export environment for the Python app and seed the search index
azd env get-values > .env
python -m venv .venv && . .venv/Scripts/Activate.ps1  # Linux/macOS: . .venv/bin/activate
# The Copilot SDK for Python is not yet on PyPI — pip installs the
# `github-copilot-sdk` package from the project's git repo.
# Requires the Copilot CLI to already be installed on PATH and signed in;
# the SDK shells out to it. See https://github.com/github/copilot-sdk.
pip install -r app/requirements.txt
python app/seed_index.py

# 4. Start the OTel Collector (forwards CLI OTLP -> App Insights)
#    Loads APPLICATIONINSIGHTS_CONNECTION_STRING from .env automatically.
docker compose --env-file .env up -d otel-collector
docker compose logs -f otel-collector   # optional — watch traces flow

# 5. Run the demo (5 scripted prompts, each in its own session)
python app/app.py

# 6. (Optional) Tear everything down after the demo
docker compose down
azd down --purge
```

## Demo prompts

Defined in [`app/prompts.json`](app/prompts.json). Designed so each Foundry evaluator has a clear story:

| # | Prompt | Expected behaviour |
| --- | --- | --- |
| 1 | "What's Northwind Bank's minimum income requirement for a personal loan?" | Grounded — Relevance & Groundedness should be high |
| 2 | "How long do I have to dispute a credit card transaction at Northwind?" | Grounded |
| 3 | "What's the current 12-month term deposit rate at Northwind?" | Grounded |
| 4 | "Compare Northwind's high-interest saver and term deposits — which is better for an emergency fund?" | Partial — forces synthesis across two docs |
| 5 | "What was Northwind Bank's 2027 Q3 profit?" | **Ungrounded** — Groundedness should fail this row (the demo punchline) |

## Cost note

While running:

- **Azure AI Search Basic** ≈ AUD 3 / day (dominant cost — billed continuously)
- **Azure OpenAI** — pay-per-token, negligible for this demo (cents)
- **Application Insights / Log Analytics** — pay-per-GB ingested, also negligible
- **Foundry account + project** — no marginal cost for the demo workload

Total expected: **~AUD 3–6 / day**. Tear down with `azd down --purge` when you're done.

## References

- [GitHub Copilot SDK — OpenTelemetry observability](https://docs.github.com/en/copilot/how-tos/copilot-sdk/observability/opentelemetry)
- [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [Azure Monitor OpenTelemetry distro for Python](https://learn.microsoft.com/azure/azure-monitor/app/opentelemetry-enable?tabs=python)
- [Azure AI Foundry — evaluate from traces](https://learn.microsoft.com/azure/ai-foundry/how-to/develop/evaluate-sdk)
- [`microsoft/skills` — foundry-agent KQL templates](https://github.com/microsoft/skills/blob/main/.github/plugins/azure-skills/skills/microsoft-foundry/foundry-agent/trace/references/kql-templates.md)

## License

[MIT](LICENSE).
