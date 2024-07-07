#!/bin/bash

daphne -b 0.0.0.0 -p 8080 whistle_server.asgi:application

wait