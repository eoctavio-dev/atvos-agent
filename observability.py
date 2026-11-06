import os
import time
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

from google.adk.telemetry.google_cloud import get_gcp_exporters, get_gcp_resource
from google.adk.telemetry.setup import maybe_set_otel_providers
from opentelemetry import metrics, trace

T = TypeVar("T")

_meter: metrics.Meter | None = None
_call_counter: metrics.Counter | None = None
_call_duration: metrics.Histogram | None = None
_error_counter: metrics.Counter | None = None


def setup_observability() -> None:
    if os.getenv("ATVOS_TELEMETRY_ENABLED", "true").lower() not in {"1", "true", "yes"}:
        return

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        return

    hooks = get_gcp_exporters(
        enable_cloud_tracing=True,
        enable_cloud_metrics=True,
        enable_cloud_logging=True,
    )
    maybe_set_otel_providers(
        otel_hooks_to_setup=[hooks],
        otel_resource=get_gcp_resource(project_id),
    )

    global _meter, _call_counter, _call_duration, _error_counter
    _meter = metrics.get_meter("atvos-agent.mcp", "1.0.0")
    _call_counter = _meter.create_counter(
        "atvos.mcp.tool.calls",
        description="Number of MCP tool calls completed",
    )
    _call_duration = _meter.create_histogram(
        "atvos.mcp.tool.duration",
        unit="s",
        description="MCP tool call duration",
    )
    _error_counter = _meter.create_counter(
        "atvos.mcp.tool.errors",
        description="Number of MCP tool calls that failed",
    )


def record_tool_call(tool: str, attributes: dict[str, str]) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(function: Callable[..., T]) -> Callable[..., T]:
        @wraps(function)
        async def wrapper(*args: object, **kwargs: object) -> T:
            started = time.perf_counter()
            status = "ok"
            span_attributes = {**attributes, "mcp.tool.name": tool}
            tracer = trace.get_tracer("atvos-agent.mcp", "1.0.0")
            with tracer.start_as_current_span(f"mcp.tool.{tool}") as span:
                span.set_attributes(span_attributes)
                try:
                    result = await function(*args, **kwargs)  # type: ignore[misc]
                    return result
                except Exception as error:
                    status = "error"
                    span.record_exception(error)
                    span.set_attribute("error.type", type(error).__name__)
                    if _error_counter is not None:
                        _error_counter.add(1, {"tool": tool, "status": status})
                    raise
                finally:
                    duration = time.perf_counter() - started
                    if _call_counter is not None:
                        _call_counter.add(1, {"tool": tool, "status": status})
                    if _call_duration is not None:
                        _call_duration.record(duration, {"tool": tool, "status": status})
                    span.set_attribute("mcp.tool.status", status)
                    span.set_attribute("mcp.tool.duration_seconds", duration)

        return wrapper

    return decorator
