# -*- coding: utf-8 -*-
from flask import request
from flask_restplus import Api, Resource, fields, reqparse

from .server import GetGeometry
from .server import GetCities

api = Api(
        version='0.1', title='Building Server API',
        description='API for accessing Building Server',
        )

# -----------------------------------------------------------------------------
# basic api
# -----------------------------------------------------------------------------
@api.route("/info")
class Test(Resource):

    def get(self):
        return "Building Server / Oslandia / contact@oslandia.com"

# -----------------------------------------------------------------------------
# core api
# -----------------------------------------------------------------------------
# getGeometry
getgeom_parser = reqparse.RequestParser()
getgeom_parser.add_argument('city', type=str, required=True)
getgeom_parser.add_argument('tile', type=str, required=True)
getgeom_parser.add_argument('format', type=str, required=False)
getgeom_parser.add_argument('attributes', type=str, required=False)

@api.route("/getGeometry")
class Read(Resource):

    @api.expect(getgeom_parser, validate=True)
    def get(self):
        args = getgeom_parser.parse_args()
        return GetGeometry().run(args)

# getCities
@api.route("/getCities")
class Read(Resource):

    def get(self):
        return GetCities().run()
