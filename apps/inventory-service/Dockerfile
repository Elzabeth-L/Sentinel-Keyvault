FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/packages/python:/app/apps/inventory-service/src
WORKDIR /app
RUN addgroup --system sentinel && adduser --system --ingroup sentinel sentinel
COPY pyproject.toml ./
COPY packages/python ./packages/python
RUN pip install --no-cache-dir .
COPY apps/inventory-service ./apps/inventory-service
USER sentinel
EXPOSE 8000
CMD ["uvicorn", "sentinel_inventory.main:app", "--host", "0.0.0.0", "--port", "8000"]
