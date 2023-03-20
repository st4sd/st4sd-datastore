#! /usr/bin/env python
#
# Copyright IBM Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Author: Vassilis Vassiliadis

"""This is a thin REST-API wrapper over experiment.service.db.Mongo methods which read/write data from/to the MongoDB"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    import pymongo.database

from werkzeug.middleware.proxy_fix import ProxyFix
from st4sd_datastore.middlelayer import PrefixMiddleware
import experiment.service.db
import pymongo
import pymongo.errors
import logging
import os
import threading
from flask_cors import CORS

import signal
import urllib.parse

unquote = urllib.parse.unquote

logging.raiseExceptions = False

FORMAT = '%(levelname)-9s %(name)-30s: %(funcName)-20s %(asctime)-15s: %(message)s'
logging.basicConfig(format=FORMAT)
rootLogger = logging.getLogger()
rootLogger.setLevel(20)

from flask import Flask, request, Blueprint
from flask_restx import Api, Resource, Namespace, reqparse, inputs
import sys
import flask_restx.apidoc

FLASK_URL_PREFIX = os.environ.get("FLASK_URL_PREFIX", "")

if FLASK_URL_PREFIX:
    old_static_url_path = flask_restx.apidoc.apidoc.static_url_path

    print(f"Prefixing SwaggerUI static url path ({old_static_url_path}) with {FLASK_URL_PREFIX}")
    flask_restx.apidoc.apidoc.static_url_path = f"{FLASK_URL_PREFIX}{old_static_url_path}"


def kill_web_server(exit_code):
    app.logger.critical("Terminating with sys.exit(%d)" % exit_code)
    with open(os.environ.get('GUNICORN_PID_PATH', "/gunicorn/webserver.pid"), 'r') as f:
        pid = int(f.read().rstrip())
    os.kill(pid, signal.Signals.SIGINT)
    sys.exit(exit_code)


app = Flask(__name__)
app.wsgi_app = PrefixMiddleware(app.wsgi_app)

app.config["LOG_TYPE"] = os.environ.get("LOG_TYPE", "watched")
app.config["LOG_LEVEL"] = os.environ.get("LOG_LEVEL", "INFO")

blueprint = Blueprint("ds-mongodb-proxy", __name__)

api = Api(
    app=blueprint,
    title="ST4SD Datastore MongoDB Proxy",
    version="1.0",
    description="REST-API interface to MongoDB database",
)

# VV: MongoDB port is typically 27017

HOST = os.environ.get('DS_BACKEND_HOST')
PORT = os.environ.get('DS_BACKEND_PORT')
USERNAME = os.environ.get('MONGODB_USERNAME', None)
PASSWORD = os.environ.get('MONGODB_PASSWORD', None)
AUTH_SOURCE = os.environ.get('MONGODB_AUTHSOURCE', None)

if HOST is None:
    rootLogger.critical("${DS_BACKEND_HOST} is undefined")
    kill_web_server(10)

if PORT is None:
    rootLogger.critical("${DS_BACKEND_PORT} is undefined")
    kill_web_server(11)

PORT = int(PORT)

rootLogger.info("Will connect to mongodb service running on %s:%d" % (HOST, PORT))

mongo: experiment.service.db.Mongo | None = None
mtx = threading.RLock()


def initialize() -> experiment.service.db.Mongo:
    """Instantiates a Mongo client and ensures that it's connected.

    If the `mongo` global variable is already instantiated this will ensure that Mongo is still connected, if the
    connection has been dropped the method will try to reconnect to mongodb. If that also fails then mongo-proxy
    will shutdown. If this is running on Kubernetes the container will be restarted.
    """
    global mongo, mtx
    with mtx:
        original_mongo = mongo
        try:
            if mongo is None:
                mongo = experiment.service.db.Mongo(
                    host=HOST, port=PORT, mongo_username=USERNAME,
                    mongo_password=PASSWORD,
                    mongo_authSource=AUTH_SOURCE, own_gateway_url=None,
                    own_gateway_id=None)
            connected = mongo.is_connected()

            if connected is False and original_mongo is None:
                raise ValueError("Unable to connect to MongoDB")
            elif connected is False and original_mongo is not None:
                del mongo
                rootLogger.info("Looks like we lost connection to MongoDB, will try to reconnect")
                mongo = None
                return initialize()
        except Exception as e:
            rootLogger.critical("Exception while connecting to MongoDB: %s - exiting" % e)
            kill_web_server(1)
        else:
            if original_mongo is None:
                rootLogger.info("Connected to MongoDB")

        return mongo


# VV: Spin up a thread that checks whether MongoDB is online in 5 seconds from now
# (gunicorn should have processed this python file by then)
init_thread = threading.Timer(5.0, function=initialize)
init_thread.setDaemon(True)
init_thread.start()

api_db_may_insert = Namespace('documents', description='Operations to interact with documents')
api_hello = Namespace('hello', description='Simple REST-API call to test whether service is running')


@api_db_may_insert.route("/api/v1.0/may-insert")
class DBMayInsert(Resource):
    def post(self):
        initialize()
        data = request.get_json(force=True)
        try:
            updated = mongo._may_update_insert_document(data['doc'], data['query'], data['update'])
        except pymongo.errors.ConnectionFailure as e:
            rootLogger.critical("Unable to may_update_insert_document with MongoDB: %s - exiting" % e)
            kill_web_server(2)

        return {'updated': updated}


@api_db_may_insert.route("/api/v1.0/upsert")
class DBUpsert(Resource):
    def post(self):
        initialize()
        data = request.get_json(force=True)
        try:
            mongo._upsert_documents(data['documents'])
        except pymongo.errors.ConnectionFailure as e:
            rootLogger.critical("Unable to upsert MongoDB: %s - exiting" % e)
            kill_web_server(3)
        return "OK"


@api_db_may_insert.route("/api/v1.0/query")
class DBQuery(Resource):
    _query_parser = reqparse.RequestParser()
    _query_parser.add_argument(
        "includeProperties",
        type=str,
        help='Comma separated columns found in the properties dataframe, or empty string, or `"*"` which is translated '
             'to "all columns in properties dataframe". Column names are case-insensitive, and the returned DataFrame '
             'will contain lowercase column names. '
             'Method silently discards columns that do not exist in DataFrame. '
             'When query returns an `experiment`-type MongoDocument it interprets the includeProperties '
             'instruction to insert a new field in `interface.propertyTable` which is a dictionary representation of a '
             'pandas.DataFrame object containing the measured properties in by $FlowIR.interface.')
    _query_parser.add_argument(
        'stringifyNaN',
        # AP - boolean values have to be parsed with this type
        # see: https://github.com/noirbizarre/flask-restplus/issues/199
        type=inputs.boolean,
        default=False,
        help='A boolean flag that allows converting NaN and infinite values to strings.',
    )

    @api.expect(_query_parser)
    def post(self):
        initialize()
        args = self._query_parser.parse_args()

        str_include_properties: str | None = args.includeProperties

        include_properties: List[str] | None = None
        if str_include_properties is not None:
            include_properties = [x.lower() for x in str_include_properties.split(',')]

        stringify_nan: bool = args.stringifyNaN

        data = request.get_json(force=True)

        def process_doc(x):
            # VV: the ObjectID key in documentDescriptors is not json-serializable
            if '_id' in x:
                del x['_id']
            return x

        try:
            # VV: This gets an Iterable of Documents instead of a List of documents. In the future we can find a way
            # so as not to maintain the entire list in memory but rather stream it.
            docs = mongo._kernel_getDocument(query=data, include_properties=include_properties,
                                             stringify_nan=stringify_nan)
        except pymongo.errors.ConnectionFailure as e:
            rootLogger.critical("Unable to query with MongoDB: %s - exiting" % e)
            kill_web_server(4)
            raise  # VV: keep linter happy
        except Exception as e:
            rootLogger.warning(f"Query {data} caused {e} - will return internal error 500")
            raise

        return {"document-descriptors": [process_doc(x) for x in docs]}


@api_hello.route("/")
class HelloAPI(Resource):
    def get(self):
        return "hello"


# api.add_resource(DBQuery, '/documents/api/v1.0/query', endpoint='query', methods=['POST'])
# api.add_resource(DBUpsert, '/documents/api/v1.0/upsert', endpoint='upsert', methods=['POST'])
# api.add_resource(DBMayInsert, '/documents/api/v1.0/may-insert', endpoint='may-insert', methods=['POST'])

# api.add_resource(HelloAPI, '/hello', endpoint='hello', methods=['GET'])

api.add_namespace(api_db_may_insert)
api.add_namespace(api_hello)

CORS(app)

app.register_blueprint(blueprint, url_prefix=FLASK_URL_PREFIX)

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# print(app.url_map)

if __name__ == '__main__':
    if len(sys.argv) >= 2:
        port = int(sys.argv[1])
    else:
        port = 5001

    app.run(debug=True, port=port, host='0.0.0.0')
