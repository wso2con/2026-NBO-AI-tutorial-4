"""Configurable manual instrumentation for MCP tool calls.

Agent Manager can auto-instrument a deployed agent with OTEL tracing (via
Traceloop) - see Module 04's "Tracing - Instrumentation" toggle. That
auto-instrumentation captures LLM/HTTP-level spans generically, but a tool
call failure surfaces to it as whatever exception shape langgraph/
langchain-mcp-adapters happen to raise - in practice a `BaseExceptionGroup`
wrapping the real cause (see `_leaf_causes()` in agent.py), which auto
-instrumentation has no reason to unwrap. The result: the trace shows a
generic tool-call error rather than the actual denial/failure reason.

This module adds a manual span around each MCP tool call that unwraps that
ExceptionGroup and records the real leaf exception - only when explicitly
enabled, since running this alongside Agent Manager's own auto
-instrumentation would duplicate traces (per Module 04's guidance: turn
auto-instrumentation off if the agent's own code is already instrumented).

Config:
- AMP_MANUAL_INSTRUMENTATION_ENABLED=true - turn this on. Default: off.
- AMP_OTEL_ENDPOINT / AMP_AGENT_API_KEY - same vars Agent Manager injects
  for its own auto-instrumentation; reused here so manual spans land in
  the same backend. Required if the toggle above is on.
- AMP_TRACE_CONTENT (default "true") - whether span attributes include
  tool call arguments/results, not just metadata. Set to "false" to
  exclude potentially sensitive payloads (account numbers, balances) from
  trace data.
"""

from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("customer-support-agent")

_ENABLED = os.environ.get("AMP_MANUAL_INSTRUMENTATION_ENABLED", "false").lower() == "true"
_TRACE_CONTENT = os.environ.get("AMP_TRACE_CONTENT", "true").lower() == "true"

_tracer = None


def init_instrumentation() -> None:
    """Initialize Traceloop for manual instrumentation, if enabled.

    No-op if AMP_MANUAL_INSTRUMENTATION_ENABLED isn't set - the default,
    so an agent relying on Agent Manager's own auto-instrumentation (the
    Module 04 default) gets no second tracer and no duplicate traces.
    """
    if not _ENABLED:
        log.info("manual instrumentation disabled (AMP_MANUAL_INSTRUMENTATION_ENABLED not set)")
        return

    otel_endpoint = os.environ.get("AMP_OTEL_ENDPOINT")
    api_key = os.environ.get("AMP_AGENT_API_KEY")
    if not otel_endpoint or not api_key:
        raise ValueError(
            "AMP_MANUAL_INSTRUMENTATION_ENABLED is set but AMP_OTEL_ENDPOINT / "
            "AMP_AGENT_API_KEY are missing - these are the same values Agent "
            "Manager injects for its own auto-instrumentation."
        )

    from traceloop.sdk import Traceloop

    os.environ["TRACELOOP_TRACE_CONTENT"] = "true" if _TRACE_CONTENT else "false"
    os.environ["TRACELOOP_METRICS_ENABLED"] = "false"

    Traceloop.init(
        telemetry_enabled=False,
        api_endpoint=otel_endpoint,
        headers={"x-amp-api-key": api_key},
    )
    log.info("manual instrumentation initialized (endpoint=%s)", otel_endpoint)


def _get_tracer():
    global _tracer
    if _tracer is None:
        from opentelemetry import trace

        _tracer = trace.get_tracer("customer-support-agent.mcp-tool-call")
    return _tracer


def _leaf_causes(exc: BaseException) -> list[BaseException]:
    """Flatten a (possibly nested) ExceptionGroup down to its leaf
    exceptions - duplicated from agent.py's helper of the same name so this
    module has no import-time dependency on agent.py.
    """
    if isinstance(exc, BaseExceptionGroup):
        leaves: list[BaseException] = []
        for sub in exc.exceptions:
            leaves.extend(_leaf_causes(sub))
        return leaves
    return [exc]


def instrument_tool(tool: Any) -> Any:
    """Wrap an MCP tool's coroutine in a span that records its *actual*
    failure, not the ExceptionGroup wrapper langgraph/langchain-mcp-adapters
    raise it in. No-op (returns tool unchanged) if instrumentation is
    disabled.

    Wrapping happens once per tool at agent-build time (not per request),
    since the span only needs to describe "this tool call", not anything
    caller-specific.
    """
    if not _ENABLED:
        return tool

    original_coroutine = tool.coroutine
    if original_coroutine is None:
        return tool

    tracer = _get_tracer()

    async def _traced_coroutine(*args: Any, **kwargs: Any) -> Any:
        from opentelemetry.trace import Status, StatusCode

        # record_exception/set_status_on_exception disabled: we record the
        # unwrapped leaf cause ourselves below, instead of letting this
        # context manager auto-record the raw ExceptionGroup wrapper on
        # exit - that's the actual bug this module exists to fix.
        with tracer.start_as_current_span(
            f"mcp.tool_call.{tool.name}",
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            span.set_attribute("mcp.tool.name", tool.name)
            if _TRACE_CONTENT:
                for key, value in kwargs.items():
                    span.set_attribute(f"mcp.tool.arg.{key}", str(value))
            try:
                result = await original_coroutine(*args, **kwargs)
            except Exception as exc:
                causes = _leaf_causes(exc)
                real_cause = causes[0] if len(causes) == 1 else exc
                span.record_exception(real_cause)
                span.set_status(Status(StatusCode.ERROR, str(real_cause)))
                raise
            span.set_status(Status(StatusCode.OK))
            return result

    tool.coroutine = _traced_coroutine
    return tool
