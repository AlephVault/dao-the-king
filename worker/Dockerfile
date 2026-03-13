FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY common/core /app/common/core
COPY worker /app/worker

RUN pip install --no-cache-dir /app/common/core
RUN pip install --no-cache-dir /app/worker

WORKDIR /app/worker

CMD ["daotheking-worker"]
