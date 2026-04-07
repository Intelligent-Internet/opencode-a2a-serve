import logging

from opencode_a2a.trace_context import (
    TraceContext,
    bind_trace_context,
    install_log_record_factory,
    parse_traceparent,
    resolve_trace_context,
)


def test_resolve_trace_context_generates_new_traceparent_when_missing() -> None:
    trace_context = resolve_trace_context(None, None)

    assert parse_traceparent(trace_context.traceparent) == (
        trace_context.traceparent,
        trace_context.trace_id,
    )
    assert trace_context.tracestate is None


def test_resolve_trace_context_drops_tracestate_when_traceparent_is_invalid() -> None:
    trace_context = resolve_trace_context("invalid", "vendor=value")

    assert parse_traceparent(trace_context.traceparent) == (
        trace_context.traceparent,
        trace_context.trace_id,
    )
    assert trace_context.tracestate is None


def test_log_record_factory_injects_current_trace_id() -> None:
    install_log_record_factory()
    logger = logging.getLogger("opencode_a2a.tests.trace_context")

    with bind_trace_context(
        TraceContext(
            traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
            tracestate=None,
        )
    ):
        record = logger.makeRecord(
            logger.name,
            logging.INFO,
            __file__,
            0,
            "trace message",
            args=(),
            exc_info=None,
        )

    assert record.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
