#!/bin/bash
#
# Copyright IBM Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Author: Vassilis Vassiliadis

my_dir='/tmp/workdir/pod-gateway-registry'

mkdir -p ${my_dir}
cd ${my_dir}
export EXTERNAL_PORT=${EXTERNAL_PORT:-"5001"}
export WORKER_TIMEOUT=${WORKER_TIMEOUT:-"120"}
export WORKER_THREADS=${WORKER_THREADS:-"1"}

export GUNICORN_PID_PATH=${GUNICORN_PID_PATH:-"/gunicorn/webserver.pid"}

gunicorn --bind "0.0.0.0:${EXTERNAL_PORT}" gateway_registry:app -p /gunicorn/webserver.pid --timeout "${WORKER_TIMEOUT}" \
      --threads "${WORKER_THREADS}"
