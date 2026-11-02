FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8765 \
    NEWS_ATLAS_DB=/app/data/news-atlas.sqlite3
WORKDIR /app
RUN groupadd --gid 1000 atlas && useradd --uid 1000 --gid atlas --no-create-home atlas \
    && mkdir /app/data && chown atlas:atlas /app/data
COPY server.py ./
COPY news_atlas/ ./news_atlas/
COPY dist/ ./dist/
COPY schema/ ./schema/
USER atlas
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/status', timeout=3).read()"
CMD ["python", "server.py"]
