#!/bin/bash
#
# Copyright IBM Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Author: Vassilis Vassiliadis

# VV: arguments: DS_BACKEND_HOST (ip), DS_BACKEND_PORT (port number)
export DS_BACKEND_HOST=${DS_BACKEND_HOST:-$ST4SD_DATASTORE_MONGODB_SERVICE_HOST}
export DS_BACKEND_PORT=${DS_BACKEND_PORT:-$ST4SD_DATASTORE_MONGODB_SERVICE_PORT}
export MONGODB_USERNAME=${MONGODB_USERNAME}
export MONGODB_PASSWORD=${MONGODB_PASSWORD}
export MONGODB_AUTHSOURCE=${MONGODB_AUTHSOURCE}

export EXTERNAL_PORT=${EXTERNAL_PORT:-"5000"}
export WORKER_TIMEOUT=${WORKER_TIMEOUT:-"120"}
export WORKER_THREADS=${WORKER_THREADS:-"2"}

export GUNICORN_PID_PATH=${GUNICORN_PID_PATH:-"/gunicorn/webserver.pid"}

gunicorn --bind "0.0.0.0:${EXTERNAL_PORT}" mongo_proxy:app -p /gunicorn/webserver.pid --timeout "${WORKER_TIMEOUT}" \
      --threads "${WORKER_THREADS}"
