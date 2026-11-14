# Minimal image for the agent's shell. No secrets, no network tools beyond Python's stdlib.
FROM python:3.11-slim
RUN pip install --no-cache-dir pytest==8.3.3
ENV PYTHONDONTWRITEBYTECODE=1 HOME=/tmp
WORKDIR /work
