"""OpenTelemetry tracing — exports to the OTel Collector, which feeds Tempo/Grafana.
Metrics continue to flow through the existing prometheus_client /metrics endpoint in main.py;
this module only adds distributed tracing on top."""
from fastapi import FastAPI

from core.config import settings


def instrument_app(app: FastAPI) -> None:
    if not getattr(settings, "OTEL_ENABLED", True):
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    except ImportError:
        # otel packages not installed — tracing is opt-in, app still runs fine without it.
        return

    resource = Resource.create({"service.name": "autoflow-api", "deployment.environment": settings.APP_ENV})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=f"{settings.OTEL_EXPORTER_ENDPOINT}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=None)  # auto-attaches to all engines


def trace_workflow_execution(execution_id: str, workflow_id: str):
    """Context manager-style span for use inside execute_workflow(). No-op if OTel isn't configured."""
    try:
        from opentelemetry import trace
        tracer = trace.get_tracer("autoflow")
        return tracer.start_as_current_span(
            "workflow.execute",
            attributes={"workflow.id": workflow_id or "", "execution.id": execution_id or ""},
        )
    except ImportError:
        from contextlib import nullcontext
        return nullcontext()
