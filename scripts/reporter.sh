#!/bin/bash
#
# Copyright IBM Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Author: Vassilis Vassiliadis

my_dir=${REPORTER_ROOT_DIR:-'/tmp/workdir/pod-reporter'}

mkdir -p ${my_dir}
cd ${my_dir}

# VV: all parameters to the script
export URL_GATEWAY_REGISTRY=${URL_GATEWAY_REGISTRY:-https://your-registry-goes-here}
export URL_LOCAL_PUBLIC=${URL_LOCAL_PUBLIC:-https://the-url-of-the-registry-within-the-cluster-goes-here}
export LOCAL_GATEWAY_ID=${LOCAL_GATEWAY_ID:-"hermes"}

# VV: arguments: DS_BACKEND_HOST (ip), DS_BACKEND_PORT (port number)
export DS_BACKEND_HOST=${DS_BACKEND_HOST:-$ST4SD_DATASTORE_MONGODB_SERVICE_HOST}
export DS_BACKEND_PORT=${DS_BACKEND_PORT:-$ST4SD_DATASTORE_MONGODB_SERVICE_PORT}
export MONGODB_USERNAME=${MONGODB_USERNAME}
export MONGODB_PASSWORD=${MONGODB_PASSWORD}
export MONGODB_AUTHSOURCE=${MONGODB_AUTHSOURCE}
export LOCAL_GATEWAY_PORT=${LOCAL_GATEWAY_PORT:-5002}
export URL_LOCAL_LOCAL=${URL_LOCAL_LOCAL:=http://127.0.0.1:${LOCAL_GATEWAY_PORT}/ds-gateway}

monitor_dir="${my_dir}/update-files"

# VV: Reporter prefers URL_MONGODB_REST_API over DS_BACKEND_HOST & DS_BACKEND_PORT (picks rest-api if both present)

reporter.py \
    --gateway-registry-url "${URL_GATEWAY_REGISTRY}" \
    --local-gateway-public-url "${URL_LOCAL_PUBLIC}" \
    --local-gateway-local-url "${URL_LOCAL_LOCAL}" \
    --local-gateway-port "${LOCAL_GATEWAY_PORT}" \
    --mongo-url "${URL_MONGODB_REST_API}" \
    --mongo-host "${DS_BACKEND_HOST}" --mongo-port "${DS_BACKEND_PORT}" \
    --monitor-dir "${monitor_dir}" \
    --mongo-username "${MONGODB_USERNAME}" \
    --mongo-password "${MONGODB_PASSWORD}" \
    --mongo-auth-source "${MONGODB_AUTHSOURCE}" \
    --gateway-id "${LOCAL_GATEWAY_ID}" 2>&1
