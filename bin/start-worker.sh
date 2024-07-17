#!/bin/bash

celery -A whistle_server worker "$@"