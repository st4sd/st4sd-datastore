#!/usr/bin/env bash
#
# Copyright IBM Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Author: Vassilis Vassiliadis

export CONFIG_NGINX=/etc/nginx/conf.d/config-nginx.conf

python /scripts/build_nginx_configuration.py ${CONFIG_NGINX} && \
nginx -g "daemon off;"
