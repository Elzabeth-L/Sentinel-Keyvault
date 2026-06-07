FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/packages/python

WORKDIR /app
RUN addgroup --system sentinel && adduser --system --ingroup sentinel sentinel
COPY pyproject.toml ./
COPY packages/python ./packages/python
RUN pip install --no-cache-dir .
COPY database ./database
USER sentinel
CMD ["alembic", "-c", "database/alembic.ini", "upgrade", "head"]
