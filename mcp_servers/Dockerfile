FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir "mcp>=1.9,<2" "httpx>=0.28" "pydantic>=2.10"
COPY mcp_servers /app/mcp_servers
ENV PYTHONPATH=/app
ENV OPSPILOT_MCP_HOST=0.0.0.0
EXPOSE 8001 8002 8003
CMD ["python", "-m", "mcp_servers.observability.server"]
