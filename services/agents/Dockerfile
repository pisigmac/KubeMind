FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/

ENV PYTHONPATH=/app/src
ENV PORT=8082

EXPOSE 8082

CMD ["uvicorn", "agents.main:app", "--host", "0.0.0.0", "--port", "8082"]
