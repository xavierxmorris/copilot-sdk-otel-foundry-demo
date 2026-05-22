# Demo Run Sheet

A scripted walkthrough of the Copilot SDK → OTel → App Insights → Foundry loop.
Designed to be talked through in ~10–15 minutes.

## Before you start

Open these tabs:

1. The repo on GitHub: <https://github.com/xavierxmorris/copilot-sdk-otel-foundry-demo>
2. **Azure portal → Resource group `rg-copilot-otel-demo`**
3. **Application Insights** (`appi-...`) → **Logs** blade
4. **Azure AI Foundry portal** → project `proj-copilot-otel-demo` → **Tracing**
5. A terminal in the repo root with `azd` env activated.

## Step 0 — Repo & infra (already done before the demo)

```bash
azd auth login
az login
az account set --subscription 51eb709f-8958-49c4-a547-ebdbd4bf66dc

azd env new copilot-otel-demo
azd env set AZURE_LOCATION eastus2
# Optional override: azd env set SEARCH_LOCATION centralus
azd up                              # ~12–15 min the first time
azd env get-values > .env
pip install -r app/requirements.txt
python app/seed_index.py            # uploads the 5 Northwind docs to Search
```

> Talking point: everything in `infra/` is one `azd up`. Foundry, App Insights,
> AOAI, Search, RBAC. The Bicep also wires up the **AppInsights connection**
> on the Foundry project, so the Tracing tab lights up automatically — no
> manual portal click.

## Step 1 — Start the OTel Collector

The Copilot SDK CLI emits OTLP, not direct App Insights. The collector bridges them.

```bash
docker compose --env-file .env up -d otel-collector
docker compose logs -f otel-collector   # optional second pane during the demo
```

> Talking point: this is a vanilla OTel Collector with the `azuremonitor`
> contrib exporter. Same shape you'd run in production.

## Step 2 — Run the agent (live)

```bash
python app/app.py
```

You'll see 5 prompts execute, one per fresh conversation:

1. Personal-loan minimum income (grounded)
2. Credit-card dispute window (grounded)
3. 12-month term deposit rate (grounded)
4. Saver vs term deposit synthesis (partial)
5. **2027 Q3 profit (ungrounded — the punchline)**

> Talking point: nothing about this code looks "observability-aware" beyond
> a small `telemetry={...}` dict on `SubprocessConfig`. The Copilot SDK
> emits the spans for free following the OTel GenAI semconv.

## Step 3 — Verify traces in Application Insights

In the App Insights **Logs** blade, paste the queries from
[`docs/kql-queries.md`](./kql-queries.md):

- Trace overview (last 30 min)
- Token usage per conversation

> Talking points:
> - `dependencies` rows have `gen_ai.operation.name` = `invoke_agent`,
>   `execute_tool`, or `chat`.
> - `customDimensions` carries the full GenAI semconv (`gen_ai.usage.input_tokens`,
>   `gen_ai.request.model`, `gen_ai.conversation.id`, …).
> - `traces` rows carry the input/output messages because we set
>   `capture_content=True`.

## Step 4 — Foundry Tracing tab

Switch to the Foundry portal → project → **Tracing**.

Click on one conversation (e.g. the credit-card dispute one). Expand the span tree:

```
invoke_agent
└── execute_tool: retrieve_docs
│   └── (HTTP child span: Azure AI Search)
└── chat (gpt-4o-mini)
```

Click the `invoke_agent` span and show the **Input** and **Output** message tabs.

> Talking point: this is exactly the same App Insights data you just queried,
> rendered as a trace tree. No second pipeline, no second store.

## Step 5 — Run Foundry evaluation against the traces

In Foundry: **Evaluation → New evaluation**.

- **Target:** `Traces`
- **Filter:** last 30 min, `gen_ai.agent.name == "rag-demo-agent"`
- **Evaluators:** Groundedness, Relevance, Coherence

Submit. While it runs:

> Talking point: this is the killer feature. Most eval tools want you to
> construct a dataset. Foundry can grade your **real production traffic**
> straight from App Insights.

When it finishes, run the **eval-results KQL** in
[`docs/kql-queries.md`](./kql-queries.md) and show that:

- Rows 1, 2, 3 score high on Groundedness.
- Row 4 scores medium (partial synthesis).
- **Row 5 (the 2027 profit prompt) fails Groundedness** — exactly as designed.

> Closing talking point: this is how observability becomes measurable quality.
> Same loop you'd run nightly across all production traffic with custom
> evaluators on top.

## Step 6 — Teardown

```bash
docker compose down
azd down --purge
```

Confirms removal of every resource and the soft-deleted Cognitive Services
accounts so the next `azd up` works cleanly.
