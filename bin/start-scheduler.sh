#!/bin/bash

celery -A whistle beat -S redbeat.RedBeatScheduler "$@"