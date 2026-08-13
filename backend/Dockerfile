FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .python-version ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

RUN pip install --no-cache-dir uv \
    && uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

EXPOSE 8000

CMD ["uvicorn", "cr_portal.main:app", "--host", "0.0.0.0", "--port", "8000"]
