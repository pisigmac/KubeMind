FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/

ENV PYTHONPATH=/app/src
ENV PORT=8081

EXPOSE 8081

CMD ["uvicorn", "mind.main:app", "--host", "0.0.0.0", "--port", "8081"]
