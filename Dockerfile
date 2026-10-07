FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app

# Copy dependency files first for layer caching — deps only reinstall when these change
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-cache --no-install-project

# Copy application code
COPY gsc_server.py .

# Network defaults for container use: streamable HTTP on all interfaces, OAuth
# token and credential files in the /data volume. Set MCP_AUTH_TOKEN at runtime.
ENV MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=3001 \
    GSC_CONFIG_DIR=/data
VOLUME /data
EXPOSE 3001

HEALTHCHECK --interval=60s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"MCP_PORT\"]}/healthz', timeout=4)"

CMD ["uv", "run", "--no-sync", "python", "gsc_server.py"]
