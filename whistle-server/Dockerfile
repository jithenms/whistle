FROM python:3.11-slim-buster

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

COPY whistle-server/requirements.txt .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY whistle-server .

COPY bin/start-api.sh /usr/local/bin/start-api.sh
COPY bin/start-websockets.sh /usr/local/bin/start-websockets.sh
COPY bin/start-worker.sh /usr/local/bin/start-worker.sh
RUN chmod +x /usr/local/bin/start-api.sh /usr/local/bin/start-websockets.sh /usr/local/bin/start-worker.sh