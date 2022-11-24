#! /usr/bin/env python
#
# Copyright IBM Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Author: Vassilis Vassiliadis

import logging
import traceback
import urllib.parse
import datetime

import stream_zip

unquote = urllib.parse.unquote


logging.raiseExceptions = False

FORMAT = '%(levelname)-9s %(threadName)-30s %(name)-30s: %(funcName)-20s %(asctime)-15s: %(message)s'
logging.basicConfig(format=FORMAT)
rootLogger = logging.getLogger()
rootLogger.setLevel(20)

logFile = 'cluster_gateway.log'
handler = logging.FileHandler(logFile)
handler.setFormatter(rootLogger.handlers[0].formatter)
rootLogger.addHandler(handler)

import urllib.parse

unquote = urllib.parse.unquote
from flask import Flask, request, Blueprint, Response
from flask_restx import Api, Resource, Namespace, reqparse, fields
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from experiment.model.data import Experiment
from experiment.model.storage import ExperimentInstanceDirectory

import os
import sys
from st4sd_datastore.middlelayer import PrefixMiddleware
import flask_restx.apidoc

from st4sd_datastore.experiment_registry import ExperimentRegistry

from typing import Dict, List

FLASK_URL_PREFIX = os.environ.get("FLASK_URL_PREFIX", "")

if FLASK_URL_PREFIX:
    old_static_url_path = flask_restx.apidoc.apidoc.static_url_path

    print(f"Prefixing SwaggerUI static url path ({old_static_url_path}) with {FLASK_URL_PREFIX}")
    flask_restx.apidoc.apidoc.static_url_path = f"{FLASK_URL_PREFIX}{old_static_url_path}"

app = Flask(__name__)
app.wsgi_app = PrefixMiddleware(app.wsgi_app)

app.config["LOG_TYPE"] = os.environ.get("LOG_TYPE", "watched")
app.config["LOG_LEVEL"] = os.environ.get("LOG_LEVEL", "INFO")

blueprint = Blueprint("ds-registry", __name__)

api = Api(
    app=blueprint,
    title="Centralized Database - Gateway",
    version="1.0",
    description="Gateway to files of experiments that this workflow stack instance executed",
)

api_files = Namespace('files', description='')
api_file = Namespace('file', description='')
api_experiment = Namespace('experiment', description='')
api_hello = Namespace('hello', description='Simple REST-API call to test whether service is running')



@api_hello.route("/")
class HelloAPI(Resource):
    def get(self):
        return "hello"

os.umask(0o002)
registry_exps = ExperimentRegistry()

DS_FILE_MAX_SIZE = os.environ.get('DS_FILE_MAX_SIZE')
DS_MAX_FILES_PER_EXPERIMENT = os.environ.get('DS_MAX_FILES_PER_EXPERIMENT')
DS_MAX_FILES_TOTAL = os.environ.get('DS_MAX_FILES_TOTAL')

_def_ds_file_max_size = 32 * 1024 * 1024
_def_max_files_total = 1000
_def_ds_max_files_per_experiment = None


if DS_FILE_MAX_SIZE is None:
    rootLogger.warning("DS_FILE_MAX_SIZE environment variable not set, will default to %d bytes" % _def_ds_file_max_size)
    DS_FILE_MAX_SIZE = _def_ds_file_max_size
else:
    try:
        DS_FILE_MAX_SIZE = int(DS_FILE_MAX_SIZE)
    except Exception:
        rootLogger.warning("Could not convert DS_FILE_MAX_SIZE=\"%s\" to an integer, "
                           "will default to %d bytes" % (DS_FILE_MAX_SIZE, _def_ds_file_max_size))
        DS_FILE_MAX_SIZE = _def_ds_file_max_size
    else:
        rootLogger.warning("DS_FILE_MAX_SIZE is set to %d bytes" % DS_FILE_MAX_SIZE)


if DS_MAX_FILES_PER_EXPERIMENT is None:
    rootLogger.warning("DS_MAX_FILES_PER_EXPERIMENT environment variable not set, "
                       "will default to %s" % _def_ds_max_files_per_experiment)
    DS_MAX_FILES_PER_EXPERIMENT = _def_ds_max_files_per_experiment
elif DS_MAX_FILES_PER_EXPERIMENT != '':
    try:
        DS_MAX_FILES_PER_EXPERIMENT = int(DS_MAX_FILES_PER_EXPERIMENT)
    except Exception:
        rootLogger.warning("Could not convert DS_MAX_FILES_PER_EXPERIMENT=\"%s\" to an integer, "
                           "will default to %s files per experiment" % (DS_MAX_FILES_PER_EXPERIMENT,
                                                                        _def_ds_max_files_per_experiment))
        DS_MAX_FILES_PER_EXPERIMENT = _def_ds_max_files_per_experiment
    else:
        rootLogger.warning("DS_MAX_FILES_PER_EXPERIMENT is set to %s" % DS_MAX_FILES_PER_EXPERIMENT)
else:
    DS_MAX_FILES_PER_EXPERIMENT = None
    rootLogger.warning("Setting unlimited maximum files per experiment")


if DS_MAX_FILES_TOTAL is None:
    rootLogger.warning("DS_MAX_FILES_TOTAL environment variable not set, "
                       "will default to %s" % _def_max_files_total)
    DS_MAX_FILES_TOTAL = _def_max_files_total
elif DS_MAX_FILES_TOTAL != '':
    try:
        DS_MAX_FILES_TOTAL = int(DS_MAX_FILES_TOTAL)
    except Exception:
        rootLogger.warning("Could not convert DS_MAX_FILES_TOTAL=\"%s\" to an integer, "
                           "will default to %s total files" % (DS_MAX_FILES_TOTAL,
                                                                        _def_max_files_total))
        DS_MAX_FILES_TOTAL = _def_max_files_total
    else:
        rootLogger.warning("DS_MAX_FILES_TOTAL is set to %s" % DS_MAX_FILES_TOTAL)
else:
    DS_MAX_FILES_TOTAL = None
    rootLogger.warning("Setting unlimited total maximum files")


class IterableStreamZipOfDirectory:
    def __init__(self, root):
        self.location = root

    @classmethod
    def iter_file(cls, full_path):
        def iter_read(full_path=full_path):
            with open(full_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    yield chunk

        return iter_read(full_path)

    def __iter__(self):

        def yield_recursively(location: str):
            folders = [(location, '/')]
            while folders:
                abs_folder, in_zip_root = folders.pop(0)
                for f in os.listdir(abs_folder):
                    if f in ['.', '..']:
                        continue

                    full = os.path.join(abs_folder, f)
                    rel_path = os.path.join(in_zip_root, f)
                    if os.path.isdir(full):
                        folders.append((full, rel_path))
                    else:
                        stat = os.stat(full)
                        mod_time = datetime.datetime.fromtimestamp(stat.st_mtime)
                        file_mode = stat.st_mode
                        yield rel_path, mod_time, file_mode, stream_zip.ZIP_64, self.iter_file(full)

        for zipped_chunk in stream_zip.stream_zip(yield_recursively(self.location)):
            yield zipped_chunk


class IterableStreamZipOfFiles(IterableStreamZipOfDirectory):
    def __init__(self, files):
        self.files = list(files)

    def __iter__(self):
        def generator(files: List[str]):
            while files:
                rel_path = files.pop(0)
                full = os.path.abspath(rel_path)
                stat = os.stat(full)
                mod_time = datetime.datetime.fromtimestamp(stat.st_mtime)
                file_mode = stat.st_mode
                yield rel_path, mod_time, file_mode, stream_zip.ZIP_64, self.iter_file(full)

        for zipped_chunk in stream_zip.stream_zip(generator(self.files)):
            yield zipped_chunk


@api_experiment.route('/api/v1.0/location/<path:location>')
class DBExperimentAPI(Resource):
    def __init__(self, *args, **kwargs):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('location', type=str, required=True,
                                   help='Location of the experiment instance (absolute path)',
                                   location='json')

        super(DBExperimentAPI, self).__init__(*args, **kwargs)

    def get(self, location):
        location = unquote(location)

        if location.startswith('file://') is False:
            raise ValueError("Expected a file:// URI received \"%s\"" % location)

        rootLogger.info("Check whether experiment exists in \"%s\"" % location)

        return registry_exps.has_experiment(location)

    def post(self, location):
        location = unquote(location)

        if location.startswith('file://') is False:
            raise ValueError("Expected a file:// URI received \"%s\"" % location)

        rootLogger.info("Will try to load new %s" % location)

        try:
            gateway, path = Experiment.split_instance_location(location)
            expDir = ExperimentInstanceDirectory(path, attempt_shadowdir_repair=False)
            exp = Experiment(expDir, updateInstanceConfiguration=False, is_instance=True)

            rootLogger.info("Loaded:", exp.name, "from", location)

            registry_exps.register(path)
        except Exception:
            rootLogger.critical("Failed to process %s.\nEXCEPTION:%s" %(
                location, traceback.format_exc()
            ))

            return {'error': traceback.format_exc(), 'result': False}

        return {'result': True, 'error': None}

    # VV: Uncomment to enable deleting entire experiments from the Registry
    # def delete(self, location):
    #     if location != '/':
    #         location = '/' + location
    #
    #     registry_exps.delete(location)
    #
    #     return 200


def read_single_file(location, experiment=None):
    if location[0] != '/':
        location = '/' + location

    if experiment is not None:
        experiment = unquote(experiment)
        _, instance = Experiment.split_instance_location(experiment)

        if registry_exps.contains(instance, location) is False:
            raise ValueError("Instance \"%s\" does not contain \"%s\"" % (
                instance, location
            ))

    if DS_FILE_MAX_SIZE == -1:
        with open(location, 'r') as f:
            return f.read()
    else:
        stat = os.stat(location)  # type: os.stat_result
        if stat.st_size > DS_FILE_MAX_SIZE:
            rootLogger.warning("File %s will be truncated to %d because its size is %d" % (
                location, DS_FILE_MAX_SIZE, stat.st_size))
            with open(location, 'rt') as f:
                buf = f.read(n=DS_FILE_MAX_SIZE)
            buf = '\n'.join(
                (buf, 'FILE TRUNCATED to %d bytes, actual file size is %d' % (DS_FILE_MAX_SIZE, stat.st_size)))
            return buf
        else:
            with open(location, 'r') as f:
                return f.read()


@api_file.route('/api/v1.0/<path:experiment>/location/<path:location>',)
class DBFileAPI(Resource):
    def __init__(self, *args, **kwargs):

        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('location', type=str, required=True,
                                   help='Location of the File, must belong to known experiment @experiment',
                                   location='json')
        self.reqparse.add_argument('experiment', type=str, required=True,
                                   help='Root location of experiment, must be owned by this gateway',
                                   location='json')

        super(DBFileAPI, self).__init__(*args, **kwargs)

    def get(self, location, experiment):
        location = unquote(location)
        contents = read_single_file(location, experiment)
        return contents, 200

class ServeFiles:
    def discover_file_paths(self, data):
        # (Dict[str, List[str]) -> Dict[str, List[str]]
        """Receives a Dictionary of workflow instances->List[files under workflow instance] and returns those
        which are contained under the instance"""
        all_files = {}
        for exp_instance in data:

            files = ['/%s' % l if l[0] != '/' else l for l in data[exp_instance]]

            if exp_instance.startswith('file://') is False:
                raise ValueError("Expected a file:// URI but got \"%s\"" % exp_instance)

            _, exp_location = Experiment.split_instance_location(exp_instance)

            filtered_files = []
            for path in files:
                if registry_exps.contains(exp_location, path):
                    if os.path.exists(path):
                        filtered_files.append(path)

            if filtered_files:
                all_files[exp_instance] = filtered_files

        return all_files

    def select_files(self, all_files):
        # type: (Dict[str, List[str]]) -> List[str]
        """Filters all_files so that resulting list of files adheres to Datastore limiting constraints (max bytes, etc)
        """
        selected_files = []
        max_bytes_total = DS_FILE_MAX_SIZE
        max_files_per_experiment = DS_MAX_FILES_PER_EXPERIMENT
        max_files_total = DS_MAX_FILES_TOTAL

        total_bytes = 0
        total_returned_files = 0

        for exp_instance in all_files:
            if max_files_total is not None and total_returned_files >= max_files_total:
                break

            exp_returned_files = 0
            for path in all_files[exp_instance]:
                file_size = os.path.getsize(path)

                if 0 <= DS_FILE_MAX_SIZE < file_size:
                    file_size = DS_FILE_MAX_SIZE

                if file_size + total_bytes > max_bytes_total:
                    rootLogger.warning("Will not return file %s because we would exceed max "
                                       "number of bytes (%d + %d > %d)" % (
                                           path, total_bytes, file_size, max_bytes_total))
                    continue
                selected_files.append(path)

                total_bytes += file_size
                exp_returned_files += 1
                total_returned_files += 1

                if max_files_per_experiment is not None and exp_returned_files >= max_files_per_experiment:
                    rootLogger.warning("Hit maximum number of files (%d) for %s" % (
                        max_files_per_experiment, exp_instance))
                    break

                if max_files_total is not None and total_returned_files >= max_files_total:
                    rootLogger.warning("Hit maximum number of files (%d) per request" % max_files_total)
                    break

        return selected_files

mFilesMany = api_files.model('get-many-files', {
        "instanceURI": fields.List(
            fields.String("absolutePathToFile")
        )
    },
    example={
        'file://tmp/workdir/<experiment_instance_dir.instance>': [
            '/tmp/workdir/<experiment_instance_dir.instance>/output/experiment.log'
        ]
    },
)

@api_files.route('/api/v1.1')
class DBFileManyZipAPI(Resource):
    def __init__(self, *args, **kwargs):
        super(DBFileManyZipAPI, self).__init__(*args, **kwargs)
        self.files = ServeFiles()

    @api_files.expect(mFilesMany)
    def post(self):
        data = request.get_json(force=True)
        all_files = self.files.discover_file_paths(data)
        selected_files = self.files.select_files(all_files)

        response = Response(IterableStreamZipOfFiles(selected_files), mimetype='application/zip')
        response.headers['Content-Disposition'] = 'attachment; filename={}'.format('files.zip')
        return response


@api_experiment.route('/')
class ExperimentExists(Resource):
    def get(self):
        experiment = request.args.get('experiment')
        stage = request.args.get('stage')
        component = request.args.get('component')

        component = unquote(component)
        experiment = unquote(experiment)

        if experiment[0] != '/':
            experiment = '/' + experiment

        if registry_exps.has_experiment(experiment) is False:
            rootLogger.info("Unknown experiment %s" % experiment)
            return False

        experiment = unquote(experiment)
        _, instance = Experiment.split_instance_location(experiment)

        location = os.path.join(instance, 'stages', 'stage%s' % stage, component)

        return str(os.path.isdir(location))



@api_experiment.route('/download')
class ExperimentDownload(Resource):
    def get(self):
        experiment = request.args.get('experiment')
        stage = request.args.get('stage')
        component = request.args.get('component')

        component = unquote(component)
        experiment = unquote(experiment)

        if experiment[0] != '/':
            experiment = '/' + experiment

        if registry_exps.has_experiment(experiment) is False:
            rootLogger.info("Unknown experiment %s" % experiment)
            return False

        experiment = unquote(experiment)
        _, instance = Experiment.split_instance_location(experiment)

        location = os.path.join(instance, 'stages', 'stage%s' % stage, component)

        if os.path.isdir(location) is False:
            return ""

        response = Response(IterableStreamZipOfDirectory(location), mimetype='application/zip')
        response.headers['Content-Disposition'] = 'attachment; filename={}'.format('files.zip')
        return response


api.add_namespace(api_files)
api.add_namespace(api_file)
api.add_namespace(api_experiment)
api.add_namespace(api_hello)

CORS(app)

app.register_blueprint(blueprint, url_prefix=FLASK_URL_PREFIX)

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# print(app.url_map)

if __name__ == '__main__':
    if len(sys.argv) >= 2:
        port = int(sys.argv[1])
    else:
        port = 5002

    app.run(debug=True, port=port, host='0.0.0.0')