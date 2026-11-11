FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_DEBUG=0

RUN groupadd --system app \
    && useradd --system --gid app --create-home app \
    && mkdir -p /app/instance \
    && chown -R app:app /app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY run.py .

USER app
EXPOSE 5000
VOLUME ["/app/instance"]

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--access-logfile", "-", "--error-logfile", "-", "run:app"]
