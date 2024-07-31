#!/bin/bash

celery -A whistle worker -Q broadcasts,recipients,deliveries "$@" 