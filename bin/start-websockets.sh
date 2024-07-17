#!/bin/bash

daphne -b 0.0.0.0 -p 8081 whistle_server.asgi:application "$@"