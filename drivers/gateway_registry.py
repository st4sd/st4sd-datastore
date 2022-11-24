#! /usr/bin/env python
#
# Copyright IBM Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Author: Vassilis Vassiliadis

import logging
import os

logging.raiseExceptions = False

FORMAT = '%(levelname)-9s %(name)-30s: %(funcName)-20s %(asctime)-15s: %(message)s'
logging.basicConfig(format=FORMAT)
rootLogger = logging.getLogger()
rootLogger.setLevel(20)

from werkzeug.middleware.proxy_fix import ProxyFix
from st4sd_datastore.middlelayer import PrefixMiddleware
import urllib.parse

unquote = urllib.parse.unquote
from flask import Flask, request, Blueprint
from flask_restx import Api, Resource, Namespace, reqparse
import sys
import flask_restx.apidoc
from flask_cors import CORS

from st4sd_datastore.gateway_registry import GatewayRegistry

FLASK_URL_PREFIX = os.environ.get("FLASK_URL_PREFIX", "")

if FLASK_URL_PREFIX:
    old_static_url_path = flask_restx.apidoc.apidoc.static_url_path

    print(f"Prefixing SwaggerUI static url path ({old_static_url_path}) with {FLASK_URL_PREFIX}")
    flask_restx.apidoc.apidoc.static_url_path = f"{FLASK_URL_PREFIX}{old_static_url_path}"

registry = GatewayRegistry()

app = Flask(__name__)
app.wsgi_app = PrefixMiddleware(app.wsgi_app)

app.config["LOG_TYPE"] = os.environ.get("LOG_TYPE", "watched")
app.config["LOG_LEVEL"] = os.environ.get("LOG_LEVEL", "INFO")

blueprint = Blueprint("ds-registry", __name__)

api = Api(
    app=blueprint,
    title="Centralized Database - Registry of gateways",
    version="1.0",
    description="Maintains a record of known Gateways that are associated with the experiments in the database",
)

api_gateway = Namespace('gateway', description='Associate a Gateway with a domain '
                                               '(will be joined with gateways in the future)')
api_gateways = Namespace('gateways', description='Get a dictionary of known Gateway domains and their unique ids')
api_hello = Namespace('hello', description='Simple REST-API call to test whether service is running')


@api_hello.route("/")
class HelloAPI(Resource):
    def get(self):
        return "hello"


@api_gateway.route('/api/v1.0/unique_id/<string:unique_id>')
class DBGatewayAPI(Resource):
    def __init__(self, *kargs, **kwargs):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('unique_id', type=str, required=True,
                                   help='Unique id of Gateway',
                                   location='json')

        super(DBGatewayAPI, self).__init__(*kargs, **kwargs)

    def get(self, unique_id):
        return registry.get(unique_id)


@api_gateway.route('/api/v1.0/unique_id/<string:unique_id>/host/<path:host>/label/<string:label>')
class DBGatewayPostAPI(Resource):
    def __init__(self, *kargs, **kwargs):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('unique_id', type=str, required=True,
                                   help='Unique id of Gateway',
                                   location='json')
        self.reqparse.add_argument('host', type=str, required=True,
                                   help="Gateway host",
                                   location='json')
        self.reqparse.add_argument('label', type=str, required=True,
                                   help='The label of the Gateway',
                                   location='json')

        super(DBGatewayPostAPI, self).__init__(*kargs, **kwargs)

    def post(self, unique_id, host, label):
        host = unquote(host)
        registry.put(unique_id, host, label)

        return ''


@api_gateways.route('/api/v1.0/unique_ids')
class DBGatewaysAPI(Resource):
    def post(self):
        unique_ids = request.get_json(force=True)

        ret = {}

        for uid in [d for d in unique_ids if registry.contains(d)]:
            ret[uid] = registry.get(uid)

        return ret


api.add_namespace(api_gateway)
api.add_namespace(api_gateways)
api.add_namespace(api_hello)

CORS(app)

app.register_blueprint(blueprint, url_prefix=FLASK_URL_PREFIX)

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# print(app.url_map)

# api.add_resource(DBGatewayAPI,'/gateway/api/v1.0/unique_id/<string:unique_id>/host/<path:host>/label/<string:label>',
#                  endpoint='gateway',
#                  methods=['PUT', 'POST', 'DELETE'])

# api.add_resource(DBGatewayAPI, '/gateway/api/v1.0/unique_id/<string:unique_id>', endpoint='gateway_fetch', methods=['GET'])

# api.add_resource(DBGatewaysAPI, '/gateways/api/v1.0/unique_ids', endpoint='gateways_fetch', methods=['POST'])


if __name__ == '__main__':
    if len(sys.argv) >= 2:
        port = int(sys.argv[1])
    else:
        port = 5001

    app.run(debug=True, port=port, host='0.0.0.0')
