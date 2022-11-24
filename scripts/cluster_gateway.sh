#!/bin/bash
#
# Copyright IBM Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Author: Vassilis Vassiliadis

my_dir='/tmp/workdir/pod-reporter'

mkdir -p ${my_dir}
cd ${my_dir}
export EXTERNAL_PORT=${EXTERNAL_PORT:-"5002"}
export WORKER_TIMEOUT=${WORKER_TIMEOUT:-"120"}
export GUNICORN_PID_PATH=${GUNICORN_PID_PATH:-"/gunicorn/webserver.pid"}
export WORKER_THREADS=${WORKER_THREADS:-"2"}

gunicorn --bind "0.0.0.0:${EXTERNAL_PORT}" cluster_gateway:app -p /gunicorn/webserver.pid --timeout "${WORKER_TIMEOUT}" \
      --threads "${WORKER_THREADS}"
