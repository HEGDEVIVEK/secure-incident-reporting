FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:$PATH"

# Install dependencies from your lockfile.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --no-cache

# Copy application code.
COPY src ./src

# Run as a non-root user.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]