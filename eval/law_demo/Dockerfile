FROM python:3.11-slim
RUN python -m pip install --no-cache-dir pyyaml==6.0.3 pytest==9.2.0 pillow==13.0.0
WORKDIR /lab
COPY agent /lab/agent
COPY guard /lab/guard
COPY eval/demo /lab/eval/demo
COPY eval/law_demo /lab/eval/law_demo
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "eval.law_demo.container_entry"]
