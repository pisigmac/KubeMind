# Build context is the repository root so shared/ can be copied in.
#   docker build -f services/agents/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl git && rm -rf /var/lib/apt/lists/*

COPY services/agents/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/agents/src/ ./src/
COPY services/agents/config/ ./config/
COPY shared/python/ ./shared/

ENV PYTHONPATH=/app/src:/app/shared
ENV PORT=8082

EXPOSE 8082

CMD ["uvicorn", "agents.main:app", "--host", "0.0.0.0", "--port", "8082"]
