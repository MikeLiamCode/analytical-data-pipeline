FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "keye_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
