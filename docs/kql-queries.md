# KQL Queries for the Demo

All queries assume `gen_ai.agent.name = "rag-demo-agent"`. The Copilot SDK emits
spans as `dependencies` rows (not `requests`) — the OTel Collector adds the
`gen_ai.agent.name` resource attribute, so we filter on `customDimensions`
directly instead of joining onto `requests`.

Source of truth for the attribute set is the `microsoft/skills` foundry-agent
skill:
<https://github.com/microsoft/skills/blob/main/.github/plugins/azure-skills/skills/microsoft-foundry/foundry-agent/trace/references/kql-templates.md>

## 1. Trace overview (last 30 min)

```kusto
dependencies
| where timestamp > ago(30m)
| where tostring(customDimensions["gen_ai.agent.name"]) == "rag-demo-agent"
| where isnotempty(customDimensions["gen_ai.operation.name"])
| extend
    operation = tostring(customDimensions["gen_ai.operation.name"]),
    model = tostring(customDimensions["gen_ai.request.model"]),
    conv = tostring(customDimensions["gen_ai.conversation.id"])
| project timestamp, operation, name, model, conv, duration, success, operation_Id
| order by timestamp desc
```

## 2. Token usage per conversation

```kusto
dependencies
| where timestamp > ago(30m)
| where tostring(customDimensions["gen_ai.operation.name"]) == "chat"
| extend
    conv = tostring(customDimensions["gen_ai.conversation.id"]),
    in_tok = toint(customDimensions["gen_ai.usage.input_tokens"]),
    out_tok = toint(customDimensions["gen_ai.usage.output_tokens"])
| summarize calls = count(), in_tok = sum(in_tok), out_tok = sum(out_tok) by conv
| order by in_tok + out_tok desc
```

## 3. Tool execution latency

```kusto
dependencies
| where timestamp > ago(30m)
| where tostring(customDimensions["gen_ai.operation.name"]) == "execute_tool"
| extend tool = tostring(customDimensions["gen_ai.tool.name"])
| summarize calls = count(), p50 = percentile(duration, 50), p95 = percentile(duration, 95) by tool
```

## 4. Evaluation results (after Foundry eval run)

```kusto
customEvents
| where name == "gen_ai.evaluation.result"
| where timestamp > ago(1h)
| extend
    evaluator = tostring(customDimensions["gen_ai.evaluation.name"]),
    score = todouble(customDimensions["gen_ai.evaluation.score.value"]),
    label = tostring(customDimensions["gen_ai.evaluation.score.label"]),
    conv = tostring(customDimensions["gen_ai.conversation.id"]),
    explanation = tostring(customDimensions["gen_ai.evaluation.explanation"])
| project timestamp, evaluator, score, label, conv, explanation
| order by conv asc, evaluator asc
```

## 5. Join evaluation results back onto the original prompts

```kusto
let prompts =
    dependencies
    | where timestamp > ago(1h)
    | where tostring(customDimensions["gen_ai.operation.name"]) == "invoke_agent"
    | extend
        conv = tostring(customDimensions["gen_ai.conversation.id"]),
        input = tostring(customDimensions["gen_ai.input.messages"])
    | project conv, input;
let evals =
    customEvents
    | where name == "gen_ai.evaluation.result"
    | where timestamp > ago(1h)
    | extend
        conv = tostring(customDimensions["gen_ai.conversation.id"]),
        evaluator = tostring(customDimensions["gen_ai.evaluation.name"]),
        score = todouble(customDimensions["gen_ai.evaluation.score.value"]);
prompts
| join kind=inner evals on conv
| project conv, input, evaluator, score
| order by conv asc, evaluator asc
```

## Running from the Azure CLI

The Azure Portal Logs blade is the easiest place to paste these. If you want to
script them, escape the dynamic-property double quotes as single quotes inside
the `--analytics-query` value so PowerShell does not strip them:

```powershell
$appId = az monitor app-insights component show -a appi-<token> -g rg-copilot-otel-demo --query appId -o tsv
az monitor app-insights query --app $appId --analytics-query @"
dependencies
| where timestamp > ago(30m)
| where tostring(customDimensions['gen_ai.operation.name']) == 'chat'
| summarize calls=count() by tostring(customDimensions['gen_ai.request.model'])
"@ -o table
```

