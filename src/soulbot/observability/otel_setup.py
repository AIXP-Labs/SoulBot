"""Initialize OTel SDK with file exporter + metrics + fork-safety + idempotency.

Provides init_otel() + shutdown_otel() to be called from FastAPI lifespan.
Follows Doc 12 v2.3 §5.2 design:

Production-grade changes (cumulative since v1.0):
- B1: FileSpanExporter forces indent=None (JSONL integrity)
- B3: Fork-safety via os.register_at_fork (Unix only)
- B5: MeterProvider + 4 histograms (metrics.py singleton)
- B8: Resource with deployment.environment.name + service.instance.id +
       ProcessResourceDetector
- B9: PII redaction inlined in FileSpanExporter
       (OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT env controls)
- B15: Idempotent init (_INITIALIZED flag + ProxyTracerProvider check)

Environment variables consumed:
    OTEL_SERVICE_NAME                                 default "soulbot"
    SOULBOT_VERSION                                    default "dev"
    DEPLOY_ENV                                         default "dev"
    HOSTNAME                                           used if present
    SOULBOT_SPANS_FILE                                 default local path
    SOULBOT_SAMPLE_RATE                                default 1.0 (head sampler)
    SOULBOT_METRIC_CONSOLE                             "1" enables stderr metric
    OTEL_EXPORTER_OTLP_ENDPOINT                        if set, OTLP export enabled
    OTEL_EXPORTER_OTLP_PROTOCOL                        "http/protobuf" | "grpc"
    OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT default false (redact)
    OTEL_BSP_MAX_QUEUE_SIZE                            default 16384
    OTEL_BSP_SCHEDULE_DELAY                            default 2000 ms
    OTEL_BSP_MAX_EXPORT_BATCH_SIZE                     default 2048
    OTEL_BSP_EXPORT_TIMEOUT                            default 30000 ms
"""
from __future__ import annotations

import json
import logging
import os
import socket
import uuid
from pathlib import Path
from typing import Sequence

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import (
    ProcessResourceDetector,
    Resource,
    get_aggregated_resources,
)
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

from . import semconv as sc
from .otel_sampler import AlwaysKeepCriticalSampler

logger = logging.getLogger(__name__)

_INITIALIZED = False

# PII-sensitive attributes (filtered from exported spans by default).
_CAPTURE_CONTENT_ENV = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
_SENSITIVE_ATTRS = (
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.prompt",      # deprecated but safety net
    "gen_ai.completion",  # deprecated but safety net
)


class FileSpanExporter(SpanExporter):
    """Append spans as JSONL with B1 (indent=None) + B9 (PII redaction).

    v2.3 behaviour:
    - Each span serialized to a single line (`to_json(indent=None)`) so
      downstream `jq -c`, line-based tail, and LLM-viewer all work.
    - If OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT env is not "true",
      strips gen_ai.{input,output}.messages and the deprecated
      gen_ai.prompt/completion attributes from the JSON before writing.

    Note: PII redaction lives here (not in a SpanProcessor) because
    ReadableSpan.attributes is an immutable MappingProxyType after on_end;
    only the export path can rewrite attributes by re-serializing JSON.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._capture_content = os.environ.get(
            _CAPTURE_CONTENT_ENV, "false"
        ).lower() in ("true", "1", "yes")

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                for span in spans:
                    line = span.to_json(indent=None)
                    if not self._capture_content:
                        obj = json.loads(line)
                        attrs = obj.get("attributes") or {}
                        for k in _SENSITIVE_ATTRS:
                            attrs.pop(k, None)
                        obj["attributes"] = attrs
                        line = json.dumps(obj, ensure_ascii=False)
                    f.write(line + "\n")
            return SpanExportResult.SUCCESS
        except Exception as e:
            logger.warning("FileSpanExporter failed: %s", e)
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30_000) -> bool:  # noqa: D401
        return True


def _build_resource() -> Resource:
    """B8: proper Resource with required + recommended attributes."""
    attrs = {
        "service.name": os.environ.get("OTEL_SERVICE_NAME", "soulbot"),
        "service.version": os.environ.get("SOULBOT_VERSION", "dev"),
        "deployment.environment.name": os.environ.get("DEPLOY_ENV", "dev"),
        "service.instance.id": os.environ.get(
            "HOSTNAME",
            f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}",
        ),
    }
    base = Resource.create(attrs, schema_url=sc.SCHEMA_URL)
    # Auto-detect process.pid / runtime info.
    detected = get_aggregated_resources(
        [ProcessResourceDetector()],
        initial_resource=base,
    )
    return detected


def _install_metric_provider() -> None:
    """B5: MeterProvider with histograms for duration + token + ACP pool + ACP TTFT."""
    views = [
        View(
            instrument_name=sc.METRIC_OPERATION_DURATION,
            aggregation=ExplicitBucketHistogramAggregation(
                boundaries=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 25, 50],
            ),
        ),
        View(
            instrument_name=sc.METRIC_ESTIMATED_TOKEN_USAGE,  # v2.3 D1 fix
            aggregation=ExplicitBucketHistogramAggregation(
                boundaries=[1, 10, 100, 1000, 10_000, 100_000, 1_000_000],
            ),
        ),
        View(
            instrument_name=sc.METRIC_ACP_SUBPROCESS_TTFT,
            aggregation=ExplicitBucketHistogramAggregation(
                boundaries=[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
            ),
        ),
        View(
            instrument_name=sc.METRIC_ACP_POOL_QUEUE_TIME,
            aggregation=ExplicitBucketHistogramAggregation(
                boundaries=[0.001, 0.01, 0.05, 0.1, 0.5, 1, 5],
            ),
        ),
    ]
    readers = []
    if os.environ.get("SOULBOT_METRIC_CONSOLE") == "1":
        readers.append(
            PeriodicExportingMetricReader(
                ConsoleMetricExporter(), export_interval_millis=30_000
            )
        )
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        protocol = os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
        if protocol == "http/protobuf":
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
                OTLPMetricExporter,
            )
        else:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter,
            )
        readers.append(PeriodicExportingMetricReader(OTLPMetricExporter()))

    provider = MeterProvider(
        resource=_build_resource(),
        metric_readers=readers,
        views=views,
    )
    metrics.set_meter_provider(provider)


_DEFAULT_SPANS_FILE = "data/_spans.jsonl"  # mirrors soulbot_history.db location


def _install_trace_provider(spans_file: str | None = None) -> None:
    """Install TracerProvider with sampler + file + optional OTLP exporter.

    Args:
        spans_file: Override path for FileSpanExporter. Resolution order:
            1. ``SOULBOT_SPANS_FILE`` env var (highest)
            2. ``spans_file`` argument
            3. ``_DEFAULT_SPANS_FILE`` (``data/_spans.jsonl``, mirrors
               ``soulbot_history.db`` location)
    """
    fallback = ParentBased(
        TraceIdRatioBased(float(os.environ.get("SOULBOT_SAMPLE_RATE", "1.0")))
    )
    # Phase 4 Fix 11: wrap fallback so critical spans (security.*, cost.*,
    # guardrail.abort, speaker_selection, resume, etc.) are always kept even
    # when SOULBOT_SAMPLE_RATE=0.0.
    sampler = AlwaysKeepCriticalSampler(fallback)

    provider = TracerProvider(
        resource=_build_resource(),
        sampler=sampler,
    )

    spans_file = (
        os.environ.get("SOULBOT_SPANS_FILE")
        or spans_file
        or _DEFAULT_SPANS_FILE
    )
    provider.add_span_processor(
        BatchSpanProcessor(
            FileSpanExporter(spans_file),
            max_queue_size=int(os.environ.get("OTEL_BSP_MAX_QUEUE_SIZE", "16384")),
            schedule_delay_millis=int(os.environ.get("OTEL_BSP_SCHEDULE_DELAY", "2000")),
            max_export_batch_size=int(
                os.environ.get("OTEL_BSP_MAX_EXPORT_BATCH_SIZE", "2048")
            ),
            export_timeout_millis=int(
                os.environ.get("OTEL_BSP_EXPORT_TIMEOUT", "30000")
            ),
        )
    )

    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        protocol = os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
        if protocol == "http/protobuf":
            # v2.2 E1: Langfuse Cloud only supports HTTP
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
        else:
            # Stage 2/3 self-host via local Collector (gRPC)
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    trace.set_tracer_provider(provider)


def _post_fork_reinit() -> None:
    """B3: re-install provider in child process after fork (Unix only).

    Without this, BatchSpanProcessor background threads inherit parent locks
    (→ deadlock) and child atexit doesn't trigger (→ child spans never flush).
    """
    global _INITIALIZED
    _INITIALIZED = False
    _install_metric_provider()
    _install_trace_provider()
    _INITIALIZED = True
    logger.info("OTel provider re-initialized in child (pid=%d)", os.getpid())


def init_otel(spans_file: str | None = None) -> tuple[trace.Tracer, metrics.Meter]:
    """Initialize OTel. Idempotent (B15).

    Args:
        spans_file: Override file path for FileSpanExporter. Resolution order:
            1. ``SOULBOT_SPANS_FILE`` env var (highest)
            2. ``spans_file`` argument
            3. ``data/_spans.jsonl`` (default — mirrors ``soulbot_history.db`` location)

    Returns (tracer, meter). Call once from FastAPI lifespan startup.

    ⚠️ B3: DO NOT use `uvicorn --workers N` (fork semantics confuse BSP).
    Use gunicorn+UvicornWorker, or run N containers behind a load balancer.
    SoulBot dev_mode is single-process so this is fine.
    """
    global _INITIALIZED
    if _INITIALIZED:
        logger.info("init_otel: already initialized, skipping")
        return (trace.get_tracer("soulbot"), metrics.get_meter("soulbot"))

    provider_name = trace.get_tracer_provider().__class__.__name__
    if provider_name not in ("ProxyTracerProvider", "NoOpTracerProvider"):
        logger.warning(
            "init_otel: existing provider=%s; re-init may conflict.",
            provider_name,
        )

    _install_metric_provider()
    _install_trace_provider(spans_file=spans_file)

    # B3: register fork hook ONCE (Unix only; Windows lacks fork).
    if hasattr(os, "register_at_fork"):
        os.register_at_fork(after_in_child=_post_fork_reinit)

    _INITIALIZED = True
    return (trace.get_tracer("soulbot"), metrics.get_meter("soulbot"))


def shutdown_otel(timeout_millis: int = 30_000) -> None:
    """Properly flush then shutdown (Doc 12 §5.1 B6).

    `TracerProvider.shutdown()` has a 30s hard timeout since OTel 1.39+;
    we force_flush explicitly first and log if incomplete.
    """
    tracer_provider = trace.get_tracer_provider()
    meter_provider = metrics.get_meter_provider()

    if hasattr(tracer_provider, "force_flush"):
        success = tracer_provider.force_flush(timeout_millis=timeout_millis)
        if not success:
            logger.warning(
                "OTel trace flush incomplete on shutdown (queued spans may be lost)"
            )
        try:
            tracer_provider.shutdown()
        except Exception as e:
            logger.warning("OTel tracer shutdown error: %s", e)

    if hasattr(meter_provider, "force_flush"):
        success = meter_provider.force_flush(timeout_millis=timeout_millis)
        if not success:
            logger.warning("OTel metric flush incomplete on shutdown")
        try:
            meter_provider.shutdown()
        except Exception as e:
            logger.warning("OTel meter shutdown error: %s", e)
