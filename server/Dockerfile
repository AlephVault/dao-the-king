FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY common/core /app/common/core
COPY server /app/server

RUN pip install --no-cache-dir /app/common/core
RUN pip install --no-cache-dir /app/server

WORKDIR /app/server

CMD ["streamlit", "run", "src/daotheking/server/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
