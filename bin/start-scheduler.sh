#!/bin/bash

celery -A whistle_server beat -S redbeat.RedBeatScheduler "$@"