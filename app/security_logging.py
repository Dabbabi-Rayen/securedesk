import json
import logging
import sys
from datetime import datetime, timezone

from flask import has_request_context, request


security_logger = logging.getLogger("securedesk.security")


def configure_security_logging():
    security_logger.setLevel(logging.INFO)
    security_logger.propagate = True
    if not any(
        getattr(handler, "_securedesk_security", False)
        for handler in security_logger.handlers
    ):
        handler = logging.StreamHandler(sys.stdout)
        handler._securedesk_security = True
        handler.setFormatter(logging.Formatter("%(message)s"))
        security_logger.addHandler(handler)


def log_security_event(event, **details):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **details,
    }
    if has_request_context():
        record.update(
            {
                "method": request.method,
                "path": request.path,
                "remote_addr": request.remote_addr,
            }
        )
    security_logger.info(json.dumps(record, sort_keys=True))
