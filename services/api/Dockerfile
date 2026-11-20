FROM python:3.13.9-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN groupadd --system --gid 10001 agrinexa && useradd --system --uid 10001 --gid agrinexa --home-dir /nonexistent agrinexa
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --requirement requirements.txt
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
COPY app ./app
RUN mkdir -p /var/lib/agrinexa/photos /var/lib/agrinexa/datasets && chown -R agrinexa:agrinexa /var/lib/agrinexa
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/live', timeout=3).read()"]
STOPSIGNAL SIGTERM
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-graceful-shutdown", "30", "--no-access-log"]
