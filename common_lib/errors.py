class ServiceError(Exception):
    """Base exception for service-layer failures."""

    status_code = 500

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code
        self.detail = message


class ValidationError(ServiceError):
    status_code = 400


class NotFoundError(ServiceError):
    status_code = 404


class ConfigurationError(ServiceError):
    status_code = 500


class DependencyError(ServiceError):
    status_code = 502


def to_http_exception(exc: Exception):
    """Return a FastAPI HTTPException when available; otherwise fall back to a plain exception."""
    status_code = getattr(exc, "status_code", 500)
    detail = getattr(exc, "detail", str(exc) or exc.__class__.__name__)

    try:
        from fastapi import HTTPException

        return HTTPException(status_code=status_code, detail=detail)
    except ImportError:
        return RuntimeError(detail)
