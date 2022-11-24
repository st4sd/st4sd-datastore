#! /usr/bin/env python
# coding=UTF-8
#
# Copyright IBM Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Author: Vassilis Vassiliadis


import os
import sys
from typing import Dict
from typing import Tuple
import pprint


def get_services_configurations() -> Dict[str, Tuple[str, str, int]]:
    # Returns {"<service name>": (Location prefix, IP, port), ...}

    possible = {
        'ds-gateway': {
            'location': 'NGINX_SERVER_DATASTORE_GATEWAY',
            'prefix-k8s-env-vars': 'KUBERNETES_PREFIX_DATASTORE_GATEWAY',
        },
        'ds-gateway-registry': {
            'location': 'NGINX_SERVER_DATASTORE_GATEWAY_REGISTRY',
            'prefix-k8s-env-vars': 'KUBERNETES_PREFIX_DATASTORE_GATEWAY_REGISTRY',
        },
        'ds-mongo-proxy': {
            'location': 'NGINX_SERVER_DATASTORE_MONGO_PROXY',
            'prefix-k8s-env-vars': 'KUBERNETES_PREFIX_DATASTORE_MONGO_PROXY',
        },
        'runtime-service': {
            'location': 'NGINX_SERVER_RUNTIME_SERVICE',
            'prefix-k8s-env-vars': 'KUBERNETES_PREFIX_RUNTIME_SERVICE',
        },
        'registry-ui': {
            'location': 'NGINX_SERVER_REGISTRY_UI',
            'prefix-k8s-env-vars': 'KUBERNETES_PREFIX_REGISTRY_UI',
        },
    }

    ret = {}

    for x in possible:
        if possible[x]['location'] in os.environ:
            env_k8s_prefix = os.environ[possible[x]['prefix-k8s-env-vars']]

            env_k8s_ip_address = f"{env_k8s_prefix}_TCP_ADDR"
            env_k8s_port = f"{env_k8s_prefix}_TCP_PORT"

            env_k8s_ip_address = os.environ[env_k8s_ip_address]
            env_k8s_port = int(os.environ[env_k8s_port])

            ret[x] = (os.environ[possible[x]['location']], env_k8s_ip_address, env_k8s_port)

    return ret


def generate_nginx_for_service(
        location: str,
        service_ip_address: str,
        service_port: int,
        proxy_uri: str = "",
    ) -> str:
    blueprint = f"""  location /{location} {{   
    proxy_pass http://{service_ip_address}:{service_port}{proxy_uri};
    
    proxy_redirect     off;

    proxy_set_header   Host                 $host;
    proxy_set_header   X-Real-IP            $remote_addr;
    proxy_set_header   X-Forwarded-For      $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto    $scheme;
  }}
"""

    return blueprint


def main():
    output = sys.argv[1]
    nginx_port = int(os.environ.get("NGINX_PORT", 5003))
    print("Reading Services Configuration")

    configs = get_services_configurations()

    print("Configurations:")
    pprint.pprint(configs)

    nginx_config = [
        # "# configure hash buckets of nginx to deal with long server names (domains)",
        # "server_names_hash_bucket_size 512;",
        # "server_names_hash_max_size 1024;",
        "server {",
        #"  error_log stderr debug;",
        f"  listen {nginx_port} default_server;",
        f"  listen [::]:{nginx_port};",
        # VV: nginx performs urldecoding/encoding, undo it here
        # "  set $plain_uri $request_uri;",
        # "  if ( $plain_uri ~ (.*)\?.* ) {",
        # "    set $plain_uri $1 ;",
        # "  }",
        # "  rewrite .* $plain_uri last;",
        "  ",
    ]

    for x in configs:
        nginx_config.append(f"# configuration for {x}")
        nginx_config.append(
            generate_nginx_for_service(configs[x][0],  configs[x][1], configs[x][2]))

    if 'runtime-service' in configs:
        nginx_config.append(f"# Redirecting default traffic to {configs['runtime-service'][0]}")
        nginx_config.append(
            generate_nginx_for_service('', configs['runtime-service'][1], configs['runtime-service'][2],
                                       f"/{configs['runtime-service'][0]}"))

    # VV: Finally, disable nginx status
    nginx_config.extend("""location /nginx_status {
 	    deny all;		# nothing to see here	
    }
    
    location /nginx_status/ {
 	    deny all;		# nothing to see here	
    }
    """.split("\n"))

    nginx_config.append("}")

    complete_config = "\n".join(nginx_config)

    print(f"{output} contents:\n{complete_config}")

    with open(output, 'wt') as f:
        f.write(complete_config)

    print(f"Generated {output} to configure nginx running on port {nginx_port}")


if __name__ == '__main__':
    main()
