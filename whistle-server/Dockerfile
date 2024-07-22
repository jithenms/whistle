FROM python:3.11-slim-buster

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

RUN addgroup --system django \
    && adduser --system --ingroup django django

COPY whistle-server/requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY whistle-server .

COPY bin/start-api.sh /usr/local/bin/start-api.sh
COPY bin/start-websockets.sh /usr/local/bin/start-websockets.sh
COPY bin/start-worker.sh /usr/local/bin/start-worker.sh
COPY bin/start-scheduler.sh /usr/local/bin/start-scheduler.sh

RUN chmod +x /usr/local/bin/start-api.sh /usr/local/bin/start-websockets.sh /usr/local/bin/start-worker.sh /usr/local/bin/start-scheduler.sh
RUN chown django /usr/local/bin/start-api.sh /usr/local/bin/start-websockets.sh /usr/local/bin/start-worker.sh /usr/local/bin/start-scheduler.sh

USER django