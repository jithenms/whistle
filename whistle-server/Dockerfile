FROM python:3.11-slim-buster

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

COPY . .
RUN pip install --upgrade pip
RUN pip install -r /requirements.txt