#! /usr/bin/env python
#
# Copyright IBM Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Author: Vassilis Vassiliadis

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import sys
import time
import traceback

import pymongo.errors

logging.raiseExceptions = False

FORMAT = '%(levelname)-9s %(threadName)-30s %(name)-30s: %(funcName)-20s %(asctime)-15s: %(message)s'
logging.basicConfig(format=FORMAT)
rootLogger = logging.getLogger()
rootLogger.setLevel(logging.INFO)

import experiment.model.conf
import experiment.model.data
import experiment.service.db
import experiment.model.storage
from st4sd_datastore.reporter import Reporter

from typing import Dict, List, Union, Any


def consume_file(
        filepath: str,
        update: Dict[str, Any],
        exp: experiment.model.data.Experiment,
        reporter: Reporter
    ) -> bool:
    """Consumes a trigger file and upserts the associated documentDescriptions

    Args:
        filepath(str): path to trigger file (used for reporting exceptions)
        update(Dict[str, Any]): contents of trigger file
          format is {
            "platform(optional)": str,  # name of FlowIR platform that workflow instance is using
            "experiment-location": str, # path to workflow instance
            "finished-components(optional)": List[{"stage": int, "name": str}], # if missing insert entire wf instance
            "upsert-documents(optional): List[Dict[str, Any]], # a list of documents to upsert
          }

    Returns
        True if there's no exception, False otherwise

    Raises
        pymongo.errors.PyMongoError - if the connection to MongoDB is interrupted may raise this exception,
            in the background pymongo will try to re-establish connection. So you can re-execute this method
    """
    try:
        experiment_location = update['experiment-location']
        # VV: Since we're ingesting INSTANCES we should just use whatever platform the instance uses (which likely
        # will be default). The name of the platform might be different than what the WORKFLOW used to produce the
        # INSTANCE. The st4sd-runtime-core propagates the platform-specific information to the "default" platform scope
        platform = None

        if update.get('upsertExperimentDocument', False) is True:
            reporter.update_experiment_document(exp)

        if len(update.get('upsert-documents', [])) > 0:
            reporter.upsert_documents(exp, update['upsert-documents'])
        elif 'finished-components' in update:
            for comp in update['finished-components']:
                stage = comp['stage']
                name = comp['name']
                reporter.add_data(exp, stage, name, update=True)
        else:
            # VV: No finished-components, or any upsert-documents just upsert *all* docs to the db
            reporter.add_experiment(experiment_location, platform)
    except pymongo.errors.PyMongoError:
        raise
    except Exception as e:
        rootLogger.warning("Failed to consume %s\nEXCEPTION:%s" % (filepath, traceback.format_exc()))
        return False
    else:
        return True


def main():
    os.umask(0o002)

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        '--gateway-registry-url',
        help="Host (can be ip:port or domain) to report local gateway public URL",
        default='http://0.0.0.0:27018',
        required=True
    )

    parser.add_argument(
        '--local-gateway-public-url',
        help='Publicly visible URL for soon to be spawned gateway',
        default='http://drlhpsys.bx.cloud9.ibm.com/centralized-db/gateway/hartree',
        required=True
    )

    parser.add_argument('--local-gateway-local-url', help='URL to use when contacting logal gateway',
                        default="http://127.0.0.1:30096", required=True)

    parser.add_argument(
        '--local-gateway-port',
        help='Port to bind local gateway',
        default=30096,
        type=int,
        required=True
    )

    parser.add_argument(
        '--mongo-host',
        help='Host to mongoDB server',
        default='0.0.0.0',
        required=True
    )

    parser.add_argument(
        '--mongo-port', type=int,
        help='Port that the mongoDB server is listening at (on @--mongo-host)',
        default=27017,
        required=True
    )

    parser.add_argument(
        '--mongo-url', type=str,
        help='Url of mongo_proxy (will only be used if @host and @port are empty)',
        default='http://drlhpsys.bx.cloud9.ibm.com/centralized-db/db-mongo-remote',
        required=False
    )

    parser.add_argument(
        '--monitor-dir',
        help='Path to directory which elaunch.py instances will populate with information about '
             'new experiments',
        default='/gpfs/cds/local/HCRI003/rla09/shared/experiment_discoverer',
        required=True,
    )

    parser.add_argument(
        '--gateway-id',
        help='Gateway id, leave blank to generate one based on mac-address',
        default='',
        required=False,
    )

    parser.add_argument(
        '--mongo-username', help="Username to use for authentication to the MongoDB (can only"
                                 "be used when directly connecting to the DB)",
        dest="username", default=None, required=False
    )

    parser.add_argument(
        '--mongo-password', help="Password to use for authentication to the MongoDB (can only"
                                 "be used when directly connecting to the DB)",
        dest="password", default=None, required=False
    )

    parser.add_argument(
        '--mongo-auth-source', help="AuthenticationSource to use for authentication to the MongoDB (can only"
                                 "be used when directly connecting to the DB)",
        dest="auth_source", default=None, required=False
    )

    args = parser.parse_args()

    dir_monitor = args.monitor_dir
    dir_processed = os.path.join(dir_monitor, 'processed')
    dir_invalid = os.path.join(dir_monitor, 'invalid')

    for f in [dir_monitor, dir_processed, dir_invalid]:
        if not os.path.exists(f):
            os.makedirs(f)

    rootLogger.critical("Spawning reporter")
    try:
        reporter = Reporter(
            mongo_host=args.mongo_host,
            mongo_port=args.mongo_port,
            mongo_url=args.mongo_url,
            gateway_registry_url=args.gateway_registry_url,
            local_gateway_public_url=args.local_gateway_public_url,
            local_gateway_local_url=args.local_gateway_local_url,
            gateway_local_port=args.local_gateway_port,
            own_gateway_id=args.gateway_id,
            mongo_username=args.username,
            mongo_password=args.password,
            mongo_authSource=args.auth_source,
        )
    except Exception as e:
        import pprint
        rootLogger.critical("Could not spawn reporter: %s" % str(e))

        sys.exit(1)

    rootLogger.critical("Reporter spawned")

    def path_to_int(path):
        file_name = os.path.splitext(path)[0]
        number_or_begin = file_name.rsplit('-', 1)[1]

        try:
            return int(number_or_begin)
        except ValueError:
            if number_or_begin == 'begin':
                return -1

            raise ValueError("Invalid file \"%s\" whose name doesn't end in \"-<number>.json\" or \"-begin.json\"")

    def dump_invalid_updates(dir_monitor, dir_invalid, invalid_pending_updates):
        fpath = os.path.join(dir_monitor, 'invalid_update_file_paths.txt')

        if invalid_pending_updates:
            rootLogger.critical("I discovered some invalid update files: %s" % (
                invalid_pending_updates
            ))

            try:

                with open(fpath, 'w') as f:
                    json.dump(invalid_pending_updates, f, indent=2)
            except Exception:
                rootLogger.critical("Failed to dump invalid files to %s. EXCEPTION: %s" % (
                    fpath, traceback.format_exc()
                ))
            for k in invalid_pending_updates:
                _, file_name = os.path.split(k)
                new_path = os.path.join(dir_invalid, file_name)

                try:
                    os.rename(k, new_path)
                except Exception as e:
                    pass

        else:
            try:
                if os.path.exists(fpath):
                    os.remove(fpath)
            except Exception:
                rootLogger.critical("Failed to DELETE %s (no invalid update files this time around). EXCEPTION %s" % (
                    fpath, traceback.format_exc()
                ))

    try:
        while True:
            # VV: Wait 10 secs between consecutive checks of the FS, also wait 10 secs for the very first time
            #     so that the gateway has enough time to spawn

            time.sleep(10)

            pending = glob.glob(os.path.join(dir_monitor, '*.json'))

            if not pending:
                continue

            valid_pending = []
            invalid_pending_updates = []

            for p in pending:
                try:
                    path_to_int(p)
                except Exception:
                    invalid_pending_updates.append(p)
                else:
                    valid_pending.append(p)

            if invalid_pending_updates:
                dump_invalid_updates(dir_monitor, dir_invalid, invalid_pending_updates)

            if not valid_pending:
                continue

            rootLogger.info("Will process updates from %s" % valid_pending)

            pending_annotated = [{'step': path_to_int(e), 'update-file': e} for e in valid_pending]
            pending_sorted = sorted(pending_annotated, key=lambda e: e['step'])

            experiment_instances = dict()  # type: Dict[str, List[Dict[str, Union[int, str]]]]

            # VV: Group experiment updates based on their experiment instance

            for e in pending_sorted:
                filepath = e['update-file']

                try:
                    with open(filepath, 'r') as f:
                        update = json.load(f)

                    try:
                        experiment_location = update['experiment-location']
                    except KeyError:
                        raise ValueError("Key \"experiment-location\" not found in %s" % filepath)

                    if experiment_location not in experiment_instances:
                        experiment_instances[experiment_location] = [e]
                    else:
                        experiment_instances[experiment_location].append(e)

                except Exception as e:
                    rootLogger.critical("Exception: %s. Failed to parse json %s\nEXCEPTION:%s" % (
                        e, filepath, traceback.format_exc()
                    ))
                    rootLogger.critical("Did not read/decode %s add it to invalid_pending_updates" % filepath)
                    invalid_pending_updates.append(filepath)

            if invalid_pending_updates:
                dump_invalid_updates(dir_monitor, dir_invalid, invalid_pending_updates)

            rootLogger.info("Converted %s into %s" % (
                pending_sorted, experiment_instances
            ))

            for instance in experiment_instances:
                # VV: Prioritize reading the FlowIR flavour of the experiment - other flavours e.g. DOSINI may
                # not contain the name of the platform. This will cause experiment.model.data.Experiment()
                # to consider that the experiment instance is invalid (as it does not contain the requested platform).
                other_formats = [x for x in experiment.model.conf.ExperimentConfigurationFactory.default_priority
                                 if x != 'flowir']
                try:
                    expDir = experiment.model.storage.ExperimentInstanceDirectory(instance,
                                                                            attempt_shadowdir_repair=False)
                    exp = experiment.model.data.Experiment(
                        expDir, platform=update.get('platform'), updateInstanceConfiguration=False, is_instance=True,
                        format_priority=['flowir'] + other_formats)
                except Exception as exc:
                    rootLogger.warning(traceback.format_exc())
                    rootLogger.warning("Could not read experiment instance at %s, error: %s" % (instance, exc))

                    for e in experiment_instances[instance]:
                        filepath = dict(e).get('update-file')
                        if filepath:
                            invalid_pending_updates.append(filepath)
                            filename = os.path.split(filepath)[1]
                            rootLogger.critical("Did not consume %s add it to invalid_pending_updates" % filepath)
                    continue

                for e in experiment_instances[instance]:
                    filepath = None
                    try:
                        e = dict(e)
                        filepath = e['update-file']
                        with open(filepath, 'r') as f:
                            update = json.load(f)

                        rootLogger.info("Update step %s for %s" % (
                            e['step'], filepath))

                        filename = os.path.split(filepath)[1]

                        if consume_file(filepath, update, exp, reporter):
                            os.rename(e['update-file'], os.path.join(dir_processed, filename))
                        else:
                            rootLogger.critical("Run into issue while handling %s "
                                                "add it to invalid_pending_updates" % filepath)
                            invalid_pending_updates.append(filepath)
                    except pymongo.errors.PyMongoError:
                        # VV: Panic when dealing with MongoDB errors ...
                        raise
                    except Exception as e:
                        rootLogger.warning("Failed to process update-file %s.EXCEPTION:%s\n" % (
                            e, traceback.format_exc()))
                        rootLogger.warning("Did not process %s add it to invalid_pending_updates" % filepath)
                        invalid_pending_updates.append(filepath)
            if invalid_pending_updates:
                dump_invalid_updates(dir_monitor, dir_invalid, invalid_pending_updates)

        rootLogger.critical("Gateway is dead!")
    except KeyboardInterrupt:
        rootLogger.info("Received KeyboardInterrupt - exiting")
    except pymongo.errors.PyMongoError as e:
        rootLogger.warning(traceback.format_exc())
        rootLogger.warning("PyMongo Exception %s - will terminate" % e)
        sys.exit(1)
    except Exception:
        rootLogger.critical("Unexpected Exception: %s\n" % traceback.format_exc())

    rootLogger.info("Good bye!")


if __name__ == "__main__":
    # VV: http://drlhpsys.bx.cloud9.ibm.com/centralized-db/gateway-registry is mapped to 0.0.0.0:27018 on hartree
    # VV: http://drlhpsys.bx.cloud9.ibm.com/centralized-db/db-mongo is mapped to 0.0.0.0:27017 on hartree

    main()
