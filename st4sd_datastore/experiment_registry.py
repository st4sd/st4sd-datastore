
# Copyright IBM Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Author: Vassilis Vassiliadis

import os
import threading
import json
import logging
from six import string_types

try:
    from typing import Dict, List, Set
except ImportError:
    pass


class ExperimentRegistry(object):
    def __init__(self):
        self._lock = threading.RLock()
        self._experiments = set()  # type: Set[str]
        self.log = logging.getLogger('ExperimentRegistry')

        self._cache_location = 'cache_gateway.json'

        self.load()

    def store(self):
        with self._lock:
            store_dict = list(self._experiments)
            with open(self._cache_location, 'w') as f:
                json.dump(store_dict, f, indent=2)

        del store_dict

    def load(self):
        with self._lock:
            if os.path.exists(self._cache_location):
                with open(self._cache_location, 'r') as f:
                    load_dict = json.load(f)

                    is_valid_cache = isinstance(load_dict, list)

                    invalid_entries = [d for d in load_dict if not isinstance(d, string_types)]

                    if is_valid_cache and not invalid_entries:
                        self._experiments = set(map(os.path.abspath, load_dict))
                        self.log.critical("Loaded %s experiments" % (
                            len(self._experiments)
                        ))
                    else:
                        self.log.critical("%s does not contain list of strings (paths to experiment locations), "
                                          "will not load cached information. "
                                          "Specifically: json is List: %s invalid_Entries: %s" % (
                                              self._cache_location, is_valid_cache, invalid_entries))

    def register(self, experiment_root):
        # type: (str) -> None
        if experiment_root.startswith('file://') is True:
            raise ValueError("Experiment root is expected to be an absolute path to an "
                             "experiment instance, received \"%s\"" % experiment_root)

        experiment_root = os.path.abspath(experiment_root)

        with self._lock:
            self._experiments.add(experiment_root)
            self.store()

    def delete(self, experiment_root):
        if experiment_root.startswith('file://') is True:
            raise ValueError("Experiment root is expected to be an absolute path to an "
                             "experiment instance, received \"%s\"" % experiment_root)

        experiment_root = os.path.abspath(experiment_root)

        with self._lock:
            try:
                self._experiments.remove(experiment_root)
            except KeyError:
                self.log.critical("Experiment %s does not exist" % experiment_root)
            else:
                self.log.critical("Deleted experiment %s" % experiment_root)

            self.store()

    def contains(self, experiment_root, file_path):
        if experiment_root.startswith('file://') is True:
            raise ValueError("Experiment root is expected to be an absolute path to an "
                             "experiment instance, received \"%s\"" % experiment_root)

        file_path = os.path.abspath(file_path)

        with self._lock:
            if self.has_experiment(experiment_root):
                if not experiment_root.endswith('/'):
                    experiment_root = os.path.abspath(experiment_root) + '/'

                return file_path.startswith(experiment_root)

    def has_experiment(self, experiment_root):
        if experiment_root.startswith('file://') is True:
            raise ValueError("Experiment root is expected to be an absolute path to an "
                             "experiment instance, received \"%s\"" % experiment_root)

        experiment_root = os.path.abspath(experiment_root)

        return experiment_root in self._experiments
