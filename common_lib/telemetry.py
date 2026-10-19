
import time
from typing import Tuple
import os

import psutil
import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import \
    OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter  # Optional for debugging
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

from fastapi.responses import PlainTextResponse

from prometheus_client import REGISTRY, Counter, Gauge, Histogram
from prometheus_client.openmetrics.exposition import (CONTENT_TYPE_LATEST,
                                                      generate_latest)
from starlette.middleware.base import (BaseHTTPMiddleware,
                                       RequestResponseEndpoint)
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR
from starlette.types import ASGIApp


from common_lib.config.client import ConfigApp, ConfigClient

INFO = Gauge(
    "fastapi_app_info", "FastAPI application information.", [
        "app_name"]
)
REQUESTS = Counter(
    "fastapi_requests_total", "Total count of requests by method and path.", [
        "method", "path", "app_name"]
)
RESPONSES = Counter(
    "fastapi_responses_total",
    "Total count of responses by method, path and status codes.",
    ["method", "path", "status_code", "app_name"],
)
REQUESTS_PROCESSING_TIME = Histogram(
    "fastapi_requests_duration_seconds",
    "Histogram of requests processing time by path (in seconds)",
    ["method", "path", "app_name"],
)
EXCEPTIONS = Counter(
    "fastapi_exceptions_total",
    "Total count of exceptions raised by path and exception type",
    ["method", "path", "exception_type", "app_name"],
)
REQUESTS_IN_PROGRESS = Gauge(
    "fastapi_requests_in_progress",
    "Gauge of requests by method and path currently being processed",
    ["method", "path", "app_name"],
)


#REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
#REQUEST_DURATION = Histogram("http_request_duration_seconds", "Request duration in seconds")
REQUEST_IN_PROGRESS = Gauge('http_requests_in_progress', 'HTTP Requests in progress', ['method', 'path'])
CPU_USAGE = Gauge("cpu_usage_percent", "CPU usage percent")
MEMORY_USAGE = Gauge("memory_usage_percent", "Memory usage percent")


class PrometheusMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, app_name: str = "fastapi-app") -> None:
        super().__init__(app)
        self.app_name = app_name
        INFO.labels(app_name=self.app_name).inc()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method
        path, is_handled_path = self.get_path(request)

        if not is_handled_path:
            return await call_next(request)

        REQUESTS_IN_PROGRESS.labels(
            method=method, path=path, app_name=self.app_name).inc()
        REQUESTS.labels(method=method, path=path, app_name=self.app_name).inc()
        before_time = time.perf_counter()
        try:
            response = await call_next(request)
        except BaseException as e:
            status_code = HTTP_500_INTERNAL_SERVER_ERROR
            EXCEPTIONS.labels(method=method, path=path, exception_type=type(
                e).__name__, app_name=self.app_name).inc()
            raise e from None
        else:
            status_code = response.status_code
            after_time = time.perf_counter()
            # retrieve trace id for exemplar
            span = trace.get_current_span()
            trace_id = trace.format_trace_id(
                span.get_span_context().trace_id)

            REQUESTS_PROCESSING_TIME.labels(method=method, path=path, app_name=self.app_name).observe(
                after_time - before_time, exemplar={'TraceID': trace_id}
            )
        finally:
            RESPONSES.labels(method=method, path=path,
                             status_code=status_code, app_name=self.app_name).inc()
            REQUESTS_IN_PROGRESS.labels(
                method=method, path=path, app_name=self.app_name).dec()

        return response

    @staticmethod
    def get_path(request: Request) -> Tuple[str, bool]:
        for route in request.app.routes:
            match, child_scope = route.matches(request.scope)
            if match == Match.FULL:
                return route.path, True

        return request.url.path, False


def get_metrics(request: Request = None) -> Response:
    CPU_USAGE.set(psutil.cpu_percent())
    MEMORY_USAGE.set(psutil.virtual_memory().percent)
    return Response(generate_latest(REGISTRY), headers={"Content-Type": CONTENT_TYPE_LATEST})


def setting_otlp(app: ASGIApp ) -> None:

    app_env = os.getenv('APP_ENV', 'dev').lower()
    otel_enabled = os.getenv('OTEL_ENABLED', 'false').lower()

    if app_env in {'dev', 'test'} and otel_enabled not in {'1', 'true', 'yes', 'on'}:
        logging.getLogger('service').info('OTLP disabled for %s environment', app_env)
        return

    app_name = ConfigClient.get_property(key="APP_NAME", section="DEFAULT")
    
    endpoint = f'http://{ConfigClient.get_property(key="HOST", section="OTEL_COLLECTOR")}:{ConfigClient.get_property(key="PORT", section="OTEL_COLLECTOR")}'

    #endpoint = (os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))

    resource = Resource.create({"service.name": app_name})

    ## Traces
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    tracer_provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(endpoint=endpoint +'/v1/traces')))

    # Debug
    # Optional: Add a ConsoleSpanExporter for local debugging
    #console_processor = BatchSpanProcessor(ConsoleSpanExporter())
    #tracer_provider.add_span_processor(console_processor)

    # Metrics
    otlp_metrics_exporter = OTLPMetricExporter(
        endpoint = endpoint + '/v1/metrics'
    )

    # Create a metric reader that will periodically export metrics
    reader_1 = PeriodicExportingMetricReader(
        exporter = otlp_metrics_exporter,
        export_interval_millis = 3000  # Export every 3 seconds
    )

    # Debug
    #reader_2 = PeriodicExportingMetricReader(ConsoleMetricExporter())

    meter_provider = MeterProvider(resource=resource, metric_readers=[reader_1]) #, reader_2])
    metrics.set_meter_provider(meter_provider)

    # Debug
    # Optional: Add a ConsoleSpanExporter for local debugging
    #console_processor = BatchSpanProcessor(ConsoleSpanExporter())
    #tracer.add_span_processor(console_processor)

    # Color formatter
    #logging_format = logging.getLogger('service').handlers[-1].formatter._fmt

    if int(ConfigClient.get_property(key="LOG_INSTRUMENTOR", section="LOG")):
        LoggingInstrumentor().instrument( 
            #set_logging_format=True
            #logging_format=logging_format
        )

    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)

    @app.get('/metrics', tags=["default"], status_code = 200, response_class=PlainTextResponse)
    def get_metrics():
        CPU_USAGE.set(psutil.cpu_percent())
        MEMORY_USAGE.set(psutil.virtual_memory().percent)
        return Response(generate_latest(REGISTRY), headers={"Content-Type": CONTENT_TYPE_LATEST})
