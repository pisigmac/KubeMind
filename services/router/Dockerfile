# Build context is the repository root so shared/ can be copied in.
#   docker build -f services/router/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY services/router/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/router/src/ ./src/
COPY services/router/config/ ./config/
# Sensitivity detectors shared with sentinel, so both services enforce and
# report against the same rules.
COPY shared/python/ ./shared/

ENV PYTHONPATH=/app/src:/app/shared
ENV PORT=8080

EXPOSE 8080

CMD ["uvicorn", "router.main:app", "--host", "0.0.0.0", "--port", "8080"]
