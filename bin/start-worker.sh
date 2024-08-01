#!/bin/bash

celery -A whistle worker "$@" 