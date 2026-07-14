import os
import sys
import json
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from contextvars import ContextVar

# Correlation ID context variable
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
session_id_var: ContextVar[Optional[str]] = ContextVar('session_id', default=None)
worker_id_var: ContextVar[Optional[str]] = ContextVar('worker_id', default=None)


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation ID if available
        correlation_id = correlation_id_var.get()
        if correlation_id:
            log_entry["correlationId"] = correlation_id

        # Add session ID if available
        session_id = session_id_var.get()
        if session_id:
            log_entry["sessionId"] = session_id

        # Add worker ID if available
        worker_id = worker_id_var.get()
        if worker_id:
            log_entry["workerId"] = worker_id

        # Add extra fields from record
        if hasattr(record, 'extra_data'):
            log_entry["metadata"] = record.extra_data

        # Add exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_entry, ensure_ascii=False)


class CorrelationFilter(logging.Filter):
    """Filter that adds correlation context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get()
        record.session_id = session_id_var.get()
        record.worker_id = worker_id_var.get()
        return True


def setup_structured_logging(
    service_name: str,
    level: str = "INFO",
    log_file: Optional[str] = None,
):
    """
    Configure structured JSON logging for a Python service.
    
    Args:
        service_name: Name of the service (e.g., 'moshi-worker', 'orchestrator')
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(CorrelationFilter())
    root_logger.addHandler(handler)

    # Add file handler if specified
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())
        file_handler.addFilter(CorrelationFilter())
        root_logger.addHandler(file_handler)

    # Configure structlog if available
    try:
        import structlog
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(logging, level.upper(), logging.INFO)
            ),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    except ImportError:
        pass

    return root_logger


def set_correlation_id(correlation_id: Optional[str]):
    """Set correlation ID for current context."""
    correlation_id_var.set(correlation_id)


def set_session_id(session_id: Optional[str]):
    """Set session ID for current context."""
    session_id_var.set(session_id)


def set_worker_id(worker_id: Optional[str]):
    """Set worker ID for current context."""
    worker_id_var.set(worker_id)


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())


class StructuredLogger:
    """Wrapper for structured logging with context."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def _log(self, level: str, message: str, extra: Optional[Dict[str, Any]] = None):
        log_method = getattr(self.logger, level.lower())
        if extra:
            record = logging.LogRecord(
                name=self.logger.name,
                level=getattr(logging, level.upper()),
                pathname="",
                lineno=0,
                msg=message,
                args=(),
                exc_info=None,
            )
            record.extra_data = extra
            log_method(message, extra={"extra_data": extra})
        else:
            log_method(message)

    def info(self, message: str, **kwargs):
        self._log("INFO", message, kwargs if kwargs else None)

    def warning(self, message: str, **kwargs):
        self._log("WARNING", message, kwargs if kwargs else None)

    def error(self, message: str, **kwargs):
        self._log("ERROR", message, kwargs if kwargs else None)

    def debug(self, message: str, **kwargs):
        self._log("DEBUG", message, kwargs if kwargs else None)

    def critical(self, message: str, **kwargs):
        self._log("CRITICAL", message, kwargs if kwargs else None)


# Convenience function to get a structured logger
def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)
