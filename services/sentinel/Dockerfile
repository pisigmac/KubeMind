# Build context is the repository root so shared/ can be copied in.
#   docker build -f services/sentinel/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY services/sentinel/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/sentinel/src/ ./src/
COPY services/sentinel/config/ ./config/
COPY shared/python/ ./shared/

ENV PYTHONPATH=/app/src:/app/shared
ENV PORT=8083

EXPOSE 8083

CMD ["uvicorn", "sentinel.main:app", "--host", "0.0.0.0", "--port", "8083"]
