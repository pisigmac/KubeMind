# Build context is the repository root so shared/ can be copied in.
#   docker build -f services/mind/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY services/mind/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/mind/src/ ./src/
COPY services/mind/config/ ./config/
COPY shared/python/ ./shared/

ENV PYTHONPATH=/app/src:/app/shared
ENV PORT=8081

EXPOSE 8081

CMD ["uvicorn", "mind.main:app", "--host", "0.0.0.0", "--port", "8081"]
