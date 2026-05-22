"""
Copilot SDK RAG demo agent for "Northwind Bank".

This file is a structured scaffold — the coding session will finalise the
TODO blocks once we confirm the exact Copilot SDK Python API surface
against https://github.com/github/copilot-sdk.

Flow at runtime:

    1.  configure_azure_monitor() wires the global OTel SDK to export
        spans + logs + metrics to Application Insights via the connection
        string in APPLICATIONINSIGHTS_CONNECTION_STRING.

    2.  CopilotClient is created with TelemetryConfig so that the SDK
        emits OTel spans for agent runs, LLM calls, and tool execution
        following the OTel GenAI semantic conventions.

    3.  A single tool, retrieve_docs(query), is registered. It calls
        Azure AI Search and returns the top-3 chunks from the
        northwind-kb index. Inside the tool handler we restore the
        CLI's W3C trace context so the Search HTTP call shows up as a
        child span under `execute_tool`.

    4.  run_demo() loads the 5 scripted prompts from prompts.json and
        sends each one in a fresh conversation so the Foundry
        evaluation in phase 5 has 5 distinct rows to score.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from azure.monitor.opentelemetry import configure_azure_monitor
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from dotenv import load_dotenv

# TODO(coding-session): import the Copilot SDK Python client + TelemetryConfig.
# Likely shape based on the TypeScript docs:
#
#     from copilot_sdk import CopilotClient, TelemetryConfig
#
# from copilot_sdk import CopilotClient, TelemetryConfig


SOURCE_NAME = "rag-demo-agent"
TOP_K = 3


def _bootstrap_otel() -> None:
    """Send all OTel spans/logs/metrics to Application Insights."""
    conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn:
        raise SystemExit(
            "APPLICATIONINSIGHTS_CONNECTION_STRING is not set. "
            "Run `azd env get-values > .env` after `azd up`."
        )
    configure_azure_monitor(connection_string=conn)


def _make_search_client() -> SearchClient:
    endpoint = os.environ["AZURE_AI_SEARCH_ENDPOINT"]
    index = os.environ.get("AZURE_AI_SEARCH_INDEX", "northwind-kb")
    return SearchClient(
        endpoint=endpoint,
        index_name=index,
        credential=DefaultAzureCredential(),
    )


def retrieve_docs(query: str) -> list[str]:
    """Tool body: top-K chunks from Azure AI Search."""
    client = _make_search_client()
    results = client.search(search_text=query, top=TOP_K)
    return [hit["content"] for hit in results]


def _load_prompts() -> list[dict]:
    here = Path(__file__).resolve().parent
    return json.loads((here / "prompts.json").read_text(encoding="utf-8"))


def run_demo() -> None:
    """Fire the 5 scripted Northwind Bank prompts, one per conversation."""
    prompts = _load_prompts()

    # TODO(coding-session): construct the CopilotClient with telemetry, e.g.:
    #
    #   client = CopilotClient(
    #       telemetry=TelemetryConfig(
    #           exporter_type="otlp-http",          # or default in-proc
    #           source_name=SOURCE_NAME,
    #           capture_content=True,               # populate gen_ai.input/output.messages
    #       ),
    #   )
    #
    # Then for each prompt:
    #
    #   1. Start a new session (gives a fresh gen_ai.conversation.id).
    #   2. Register the `retrieve_docs` tool on the session. In the handler,
    #      restore the CLI's trace context using
    #      opentelemetry.propagation.extract({"traceparent": invocation.traceparent,
    #                                         "tracestate": invocation.tracestate})
    #      then create a child span around the SearchClient.search call so it
    #      appears under `execute_tool` in the Foundry trace tree.
    #   3. session.send(prompt["user_message"]) and stream/collect the answer.
    #   4. Print the answer + conversation id for the demo narration.
    #
    # for prompt in prompts:
    #     ...

    for prompt in prompts:
        print(f"[{prompt['id']}]  {prompt['user_message']}")
    print(
        "\n(scaffold) — the coding session will replace this loop with "
        "real CopilotClient.session.send(...) calls once the Python SDK "
        "API is confirmed."
    )


def main() -> None:
    load_dotenv()
    _bootstrap_otel()
    run_demo()


if __name__ == "__main__":
    main()
