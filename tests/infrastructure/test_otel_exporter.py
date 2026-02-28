"""Tests for OTELExporter."""

import pytest
from chimera.infrastructure.telemetry.otel_exporter import OTELConfig, OTELExporter


class TestOTELConfig:
    def test_default_empty_endpoint(self):
        config = OTELConfig()
        assert config.endpoint == ""

    def test_localhost_http_allowed(self):
        config = OTELConfig(endpoint="http://localhost:4317")
        assert config.endpoint == "http://localhost:4317"

    def test_remote_https_allowed(self):
        config = OTELConfig(endpoint="https://remote.example.com:4317")
        assert config.endpoint == "https://remote.example.com:4317"

    def test_remote_http_rejected(self):
        with pytest.raises(ValueError, match="insecure=True"):
            OTELConfig(endpoint="http://remote.example.com:4317")

    def test_remote_http_with_insecure(self):
        config = OTELConfig(
            endpoint="http://remote.example.com:4317", insecure=True
        )
        assert config.insecure is True


class TestOTELExporter:
    def test_record_metric_buffers(self):
        config = OTELConfig(endpoint="")
        exporter = OTELExporter(config)
        exporter.record_metric("test.metric", 42.0)
        assert len(exporter._metrics_buffer) == 1
        assert exporter._metrics_buffer[0]["name"] == "test.metric"
        assert exporter._metrics_buffer[0]["value"] == 42.0

    def test_record_health_status(self):
        config = OTELConfig(endpoint="")
        exporter = OTELExporter(config)
        exporter.record_health_status("node1", "HEALTHY", 50.0, 60.0)
        assert len(exporter._metrics_buffer) == 3

    def test_record_drift_detected(self):
        config = OTELConfig(endpoint="")
        exporter = OTELExporter(config)
        exporter.record_drift_detected("node1", "HIGH", "aaa", "bbb")
        assert len(exporter._metrics_buffer) == 1

    @pytest.mark.asyncio
    async def test_export_noop_when_not_initialized(self):
        config = OTELConfig(endpoint="")
        exporter = OTELExporter(config)
        exporter.record_metric("test", 1.0)
        await exporter.export()
        # Buffer not cleared when not initialized (no-op)
        assert len(exporter._metrics_buffer) == 1

    @pytest.mark.asyncio
    async def test_export_clears_buffer_when_initialized(self):
        config = OTELConfig(endpoint="")
        exporter = OTELExporter(config)
        exporter._initialized = True  # simulate initialized
        exporter.record_metric("test", 1.0)
        await exporter.export()
        assert len(exporter._metrics_buffer) == 0

    @pytest.mark.asyncio
    async def test_initialize_without_endpoint(self):
        config = OTELConfig(endpoint="")
        exporter = OTELExporter(config)
        await exporter.initialize()
        assert exporter._initialized is False

    def test_start_span_not_initialized(self):
        config = OTELConfig(endpoint="")
        exporter = OTELExporter(config)
        span = exporter.start_span("test")
        assert span is None
