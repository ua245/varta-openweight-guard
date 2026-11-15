FROM python:3.11-slim
RUN python -m pip install --no-cache-dir pyyaml==6.0.3 pytest==9.2.0
WORKDIR /lab
COPY . /lab
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "eval.demo.container_entry"]
