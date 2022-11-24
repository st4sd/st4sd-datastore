
# Copyright IBM Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Author: Vassilis Vassiliadis

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import List, Dict, Any

import experiment.model.data
import experiment.model.graph
import experiment.model.storage
import experiment.service.db
import requests


class Reporter(object):
    def __init__(self, mongo_host, mongo_port, mongo_url,
                 database='db', collection='experiments',
                 gateway_registry_url=None, local_gateway_public_url=None,
                 local_gateway_local_url=None,
                 gateway_local_port=5002, own_gateway_id=None,
                 mongo_username=None, mongo_password=None, mongo_authSource=None):
        self._gateway_url = local_gateway_public_url
        self._gateway_local_port = gateway_local_port
        self._own_gateway_id = own_gateway_id or str(uuid.getnode())

        self.log = logging.getLogger("Reporter")
        self.log.info("Connecting")

        if mongo_url:
            if (not mongo_host) and (not mongo_port):
                self.log.info("Will attempt to connect to MongoDB proxy %s instead of %s:%s" % (
                    mongo_url, mongo_host, mongo_port))

            mongo_location = mongo_url

            self._db = experiment.service.db.MongoClient(
                remote_mongo_server_url=mongo_url,
                gateway_registry_url=gateway_registry_url,
                own_gateway_url=local_gateway_public_url,
                override_local_gateway_url=local_gateway_local_url,
                own_gateway_id=own_gateway_id,
            )
        elif mongo_host and mongo_port:
            extra_args = {}

            if mongo_username is not None:
                extra_args['mongo_username'] = mongo_username

            if mongo_password is not None:
                extra_args['mongo_password'] = mongo_password

            if mongo_authSource is not None:
                extra_args['mongo_authSource'] = mongo_authSource
            mongo_location = "%s:%s" % (mongo_host, mongo_port)
            self._db = experiment.service.db.Mongo(
                host=mongo_host, port=mongo_port,
                database=database,
                collection=collection,
                gateway_registry_url=gateway_registry_url,
                own_gateway_url=self._gateway_url,
                override_local_gateway_url=local_gateway_local_url,
                own_gateway_id=own_gateway_id,
                **extra_args
            )
        else:
            raise ValueError("Neither mongo_url option was provided, nor mongo_host/mongo_port")

        if self._db.is_connected() is False:
            self.log.critical("Failed to connect!")
            raise ValueError("Could not connect to %s" % mongo_location)
        else:
            self.log.info("Successfully connected to DB")

        local_url = local_gateway_local_url or local_gateway_public_url

        self.log.info("Attempting to connect to local gateway at %s" % local_url)
        # VV: Spend at most 5 minutes trying to get a valid response from `url_hello`
        # VV: trailing "/" is important
        url_hello = '/'.join((local_url, 'hello/'))

        until = time.time() + 5*60
        while time.time() < until:
            try:
                resp = requests.get(url_hello, verify=False)
                message = resp.json()
                if message == 'hello':
                    break
                else:
                    raise ValueError("Received \"%s\" instead of \"hello\"" % message)
            except Exception as e:
                self.log.info("Exception %s while connecting to %s - will wait 10 seconds and retry" % (
                    e, local_url))
            time.sleep(10)
        else:
            raise ValueError("Cluster Gateway appears to be dead")

        self.log.info("Successfully connected to local gateway")

    def add_experiment(self, location, platform):
        self.log.info("Adding experiment at %s" % location)

        return self._db.addExperimentAtLocation(
            location, platform, self._own_gateway_id, attempt_shadowdir_repair=False)

    def update_experiment_document(self, comp_exp: experiment.model.data.Experiment):
        """Updates the experiment Document description for an Experiment instance

        Args:
            comp_exp: experiment instance
        """
        self.log.info("Upserting experiment document for %s" % comp_exp.instanceDirectory.location)

        output_file = os.path.join(comp_exp.instanceDirectory.outputDir, 'output.json')

        wait_till = time.time() + 15
        while (wait_till - time.time() > 0) and (os.path.isfile(output_file) is False):
            self.log.warning(f"Output file {output_file} does not exist")
            time.sleep(1.0)

        doc = comp_exp.generate_experiment_document_description(self._own_gateway_id)
        self._db._upsert_documents([doc])

    def upsert_documents(self, exp: experiment.model.data.Experiment, documents: List[Dict[str, Any]]) -> None:
        """Annotates documents with instance URI and usperts them

        Arguments:
            exp: Experiment instance
            documents: List of documents to annotate and then upsert
        """
        instance_uri = exp.generate_instance_location(self._own_gateway_id)

        self.log.info(f"Upserting {len(documents)} documents for {instance_uri}")

        what_updated = []

        for doc in documents:
            doc['instance'] = instance_uri
            if doc.get('type') == 'component':
                # VV: This will also update the keys of the `producers` dictionary so that the
                # producer UIDs include the gateway ID
                cid = experiment.model.graph.ComponentIdentifier(doc['name'], doc['stage'])
                experiment.model.data.Job.annotate_document(doc, instance_uri)

                what_updated.append(cid.identifier)
            elif doc.get('type') == 'experiment':
                what_updated.append("experiment")
            elif doc.get('type') == 'user-metadata':
                what_updated.append('user-metadata')
            else:
                what_updated.append('unknown')

        self.log.info(f"Updated documents are {what_updated}")

        self._db._upsert_documents(documents)

    def add_data(
            self,
            exp: experiment.model.data.Experiment,
            stage: int,
            componentName: str,
            update: bool=False) -> bool:
        self.log.info("Adding %s:%s:%s:%s" % (
            self._own_gateway_id, exp.instanceDirectory.location, stage, componentName))

        return self._db.addData(exp, stage, componentName, update=update,
                                gateway_id=self._own_gateway_id)