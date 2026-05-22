"""
Copilot SDK RAG demo agent for "Northwind Bank".

Telemetry architecture
----------------------
The Copilot SDK starts the Copilot CLI as a subprocess and talks to it over
JSON-RPC. **All GenAI OpenTelemetry spans (agent runs, LLM calls, tool
executions) are emitted by the CLI subprocess via OTLP HTTP** — not by this
Python process.

To get those spans into Application Insights, we run a small OpenTelemetry
Collector (see `otel-collector-config.yaml` and `docker-compose.yaml`) that:
  1. Receives OTLP HTTP on port 4318.
  2. Exports to Application Insights via the `azuremonitor` exporter.

Start it with:

    docker compose up -d otel-collector

…then run this script. Trace-context is automatically propagated from the
CLI down into the tool handler below (the Python SDK restores it via the
opentelemetry-api), so any spans you create inside the handler will be
children of the `execute_tool` span.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from copilot import CopilotClient, SubprocessConfig, define_tool
from copilot.generated.session_events import (
    AssistantMessageData,
    SessionIdleData,
)
from copilot.session import PermissionHandler


SOURCE_NAME = "rag-demo-agent"
TOP_K = 3
MODEL = "gpt-5"  # Use the Copilot-hosted model; swap to "gpt-4o" etc. if preferred.


# ---------------------------------------------------------------------------
# Tool: retrieve_docs
# ---------------------------------------------------------------------------

class RetrieveDocsParams(BaseModel):
    query: str = Field(description="Natural-language search query for the Northwind Bank knowledge base.")


@define_tool(
    description=(
        "Retrieve the top relevant Northwind Bank policy snippets for the user's "
        "question. Use this before answering any question about Northwind products, "
        "fees, rates, or policies."
    ),
    skip_permission=True,
)
async def retrieve_docs(params: RetrieveDocsParams) -> str:
    """Returns the top-K chunks from Azure AI Search as a single string.

    The Copilot SDK auto-restores the CLI's trace context around this
    handler, so any spans we'd start here (or that the SearchClient HTTP
    library emits, if it's instrumented) will appear as children of the
    `execute_tool` span in App Insights / Foundry Tracing.
    """
    endpoint = os.environ["AZURE_AI_SEARCH_ENDPOINT"]
    index = os.environ.get("AZURE_AI_SEARCH_INDEX", "northwind-kb")
    search = SearchClient(
        endpoint=endpoint,
        index_name=index,
        credential=DefaultAzureCredential(),
    )
    results = list(search.search(search_text=params.query, top=TOP_K))
    if not results:
        return "No matching Northwind Bank documents were found."
    return "\n\n---\n\n".join(
        f"[{hit.get('source', 'unknown')}]\n{hit['content']}" for hit in results
    )


# ---------------------------------------------------------------------------
# Demo runner
# ---------------------------------------------------------------------------

def _load_prompts() -> list[dict]:
    return json.loads((Path(__file__).parent / "prompts.json").read_text(encoding="utf-8"))


def _telemetry_config() -> dict:
    """Telemetry config for the CLI subprocess.

    The CLI emits OTLP HTTP traces to this endpoint. The OTel Collector
    (docker compose service `otel-collector`) listens here and forwards
    to Application Insights using the Azure Monitor exporter.
    """
    return {
        "otlp_endpoint": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
        "exporter_type": "otlp-http",
        "source_name": SOURCE_NAME,
        "capture_content": True,
    }


async def _run_one(client: CopilotClient, prompt: dict) -> None:
    conversation_id = f"demo-{prompt['id']}-{uuid.uuid4().hex[:8]}"
    print(f"\n=== {prompt['id']}  (conv: {conversation_id}) ===")
    print(f"User: {prompt['user_message']}")

    async with await client.create_session(
        on_permission_request=PermissionHandler.approve_all,
        model=MODEL,
        tools=[retrieve_docs],
        session_id=conversation_id,
    ) as session:
        done = asyncio.Event()
        answer_chunks: list[str] = []

        def on_event(event):  # noqa: ANN001 - SDK callback type
            match event.data:
                case AssistantMessageData() as data:
                    answer_chunks.append(data.content)
                case SessionIdleData():
                    done.set()

        session.on(on_event)
        await session.send(prompt["user_message"])
        await done.wait()

    print("Agent:", "".join(answer_chunks).strip())


async def run_demo() -> None:
    prompts = _load_prompts()
    config = SubprocessConfig(telemetry=_telemetry_config())
    async with CopilotClient(config) as client:
        for prompt in prompts:
            await _run_one(client, prompt)


def main() -> None:
    load_dotenv()
    required = ["AZURE_AI_SEARCH_ENDPOINT"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise SystemExit(
            f"Missing required env vars: {', '.join(missing)}. "
            "Run `azd env get-values > .env` after `azd up`."
        )
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
