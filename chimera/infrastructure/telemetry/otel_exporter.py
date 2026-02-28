"""
OpenTelemetry Exporter for Chimera

Architectural Intent:
- Exports agent telemetry to OTLP-compatible backends
- Supports Prometheus, Jaeger, Zipkin, Datadog, etc.
- Follows skill2026.md observability patterns

Security:
- Endpoint defaults to empty string (must be explicitly configured)
- Non-localhost http:// endpoints rejected unless insecure=True
- Validation in __post_init__ prevents accidental plaintext export
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Any
from urllib.parse import urlparse
import asyncio
import logging
from datetime import datetime, UTC

logger = logging.getLogger(__name__)


@dataclass
class OTELConfig:
    endpoint: str = ""
    service_name: str = "chimera-agent"
    environment: str = "development"
    export_interval: int = 5
    enable_traces: bool = True
    enable_metrics: bool = True
    enable_logs: bool = True
    insecure: bool = False

    def __post_init__(self) -> None:
        if self.endpoint:
            parsed = urlparse(self.endpoint)
            is_localhost = parsed.hostname in ("localhost", "127.0.0.1", "::1")
            if parsed.scheme == "http" and not is_localhost and not self.insecure:
                raise ValueError(
                    f"Non-localhost HTTP endpoint '{self.endpoint}' requires "
                    "insecure=True or use https://. "
                    "Set insecure=True to explicitly allow plaintext export."
                )


class OTELExporter:
    """
    OpenTelemetry exporter for Chimera agents.

    Supports:
    - OTLP gRPC/HTTP export
    - Prometheus metrics
    - Jaeger traces
    - Auto-instrumentation
    """

    def __init__(self, config: OTELConfig):
        self.config = config
        self._initialized = False
        self._metrics_buffer: list[dict[str, Any]] = []
        self._traces_buffer: list[dict[str, Any]] = []
        self._meter: Any = None
        self._gauges: dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialize OpenTelemetry SDK and exporters."""
        if not self.config.endpoint:
            logger.info("OTEL endpoint not configured, telemetry disabled")
            return

        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.resources import Resource, SERVICE_NAME
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry import metrics
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter,
            )

            resource = Resource(
                attributes={
                    SERVICE_NAME: self.config.service_name,
                    "environment": self.config.environment,
                }
            )

            if self.config.enable_traces:
                trace.set_tracer_provider(TracerProvider(resource=resource))
                span_processor = BatchSpanProcessor(
                    OTLPSpanExporter(endpoint=self.config.endpoint)
                )
                trace.get_tracer_provider().add_span_processor(span_processor)

            if self.config.enable_metrics:
                metric_reader = PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=self.config.endpoint)
                )
                provider = MeterProvider(
                    resource=resource, metric_readers=[metric_reader]
                )
                metrics.set_meter_provider(provider)
                self._meter = metrics.get_meter(__name__)

            self._initialized = True

        except ImportError:
            logger.warning("OpenTelemetry SDK not installed, telemetry disabled")
            self._initialized = False
        except Exception as e:
            logger.error("Failed to initialize OTEL: %s", e)
            self._initialized = False

    def _get_gauge(self, name: str, unit: str = "") -> Any:
        """Get or create a gauge for a metric name."""
        if name not in self._gauges and self._meter:
            self._gauges[name] = self._meter.create_gauge(name, unit=unit)
        return self._gauges.get(name)

    def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        attributes: Optional[dict[str, str]] = None,
    ) -> None:
        """Record a metric value."""
        self._metrics_buffer.append(
            {
                "name": name,
                "value": value,
                "unit": unit,
                "attributes": attributes or {},
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        if self._initialized:
            gauge = self._get_gauge(name, unit)
            if gauge:
                gauge.set(value, attributes=attributes or {})

    def record_health_status(
        self,
        node_id: str,
        status: str,
        cpu_percent: float = 0.0,
        memory_percent: float = 0.0,
    ) -> None:
        """Record node health metrics."""
        self.record_metric(
            "chimera.node.health",
            1.0 if status == "HEALTHY" else 0.0,
            attributes={
                "node_id": node_id,
                "status": status,
            },
        )
        self.record_metric(
            "chimera.node.cpu_percent", cpu_percent, attributes={"node_id": node_id}
        )
        self.record_metric(
            "chimera.node.memory_percent",
            memory_percent,
            attributes={"node_id": node_id},
        )

    def record_drift_detected(
        self,
        node_id: str,
        severity: str,
        expected_hash: str,
        actual_hash: str,
    ) -> None:
        """Record drift detection event."""
        self.record_metric(
            "chimera.drift.detected",
            1.0,
            attributes={
                "node_id": node_id,
                "severity": severity,
            },
        )

    def record_healing(
        self,
        node_id: str,
        success: bool,
        duration_ms: float,
    ) -> None:
        """Record healing action."""
        self.record_metric(
            "chimera.healing.duration_ms",
            duration_ms,
            attributes={
                "node_id": node_id,
                "success": str(success),
            },
        )

    def start_span(
        self,
        name: str,
        attributes: Optional[dict[str, str]] = None,
    ) -> Optional[Any]:
        """Start a tracing span."""
        if not self._initialized:
            return None

        try:
            from opentelemetry import trace

            tracer = trace.get_tracer(__name__)
            span = tracer.start_span(name, attributes=attributes or {})
            return span
        except Exception:
            return None

    def end_span(self, span: Any) -> None:
        """End a tracing span."""
        if span:
            try:
                span.end()
            except Exception:
                pass

    async def export(self) -> None:
        """Export buffered telemetry via OTLP."""
        if not self._initialized:
            return

        # With the OTEL SDK initialized, metrics are auto-exported
        # via PeriodicExportingMetricReader. We just clear our local buffer.
        exported_count = len(self._metrics_buffer)
        self._metrics_buffer.clear()
        self._traces_buffer.clear()

        if exported_count:
            logger.debug("Flushed %d buffered metrics", exported_count)


async def create_exporter(
    endpoint: Optional[str] = None,
    service_name: str = "chimera",
) -> OTELExporter:
    """Factory function to create OTEL exporter."""
    config = OTELConfig(
        endpoint=endpoint or "",
        service_name=service_name,
    )
    exporter = OTELExporter(config)
    await exporter.initialize()
    return exporter
