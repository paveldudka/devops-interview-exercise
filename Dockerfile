FROM python:3.12-slim

WORKDIR /app
COPY worker.py .

USER nobody
CMD ["python", "worker.py"]
