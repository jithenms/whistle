#!/bin/bash

python manage.py migrate

gunicorn --bind 0.0.0.0:8080 whistle_server.wsgi:application "$@"