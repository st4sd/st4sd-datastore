
# Copyright IBM Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Author: Vassilis Vassiliadis

import threading
import json
import os
import logging



from typing import Dict, List, Tuple, Union


class GatewayRegistry(object):
    def __init__(self):
        self._lock = threading.RLock()
        self._gateways = {}  # type: Dict[str, Dict[str, Union[str, int]]]

        self._cache_location = 'cache_gateway_registry.json'

        self.log = logging.getLogger('GatewayRegistry')

        self.load()

    def store(self):
        with self._lock:
            with open(self._cache_location, 'w') as f:
                json.dump(self._gateways, f)

    def load(self):
        with self._lock:
            if os.path.exists(self._cache_location):
                with open(self._cache_location, 'r') as f:
                    self._gateways = json.load(f)

    def get(self, unique_id):
        self.load()

        with self._lock:
            return self._gateways[unique_id]

    def put(self, unique_id, host, label):
        with self._lock:
            self._gateways[unique_id] = {
                'unique_id': unique_id,
                'host': host,
                'label': label,
            }

            self.store()

    def delete(self, unique_id, host, label):
        entry = {
            'unique_id': unique_id,
            'host': host,
            'label': label,
        }
        with self._lock:
            assert self.get(unique_id) == entry
            del self._gateways[unique_id]

            self.store()

    def contains(self, unique_id):
        with self._lock:
            return unique_id in self._gateways
