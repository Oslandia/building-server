# -*- coding: utf-8 -*-
from flask import request
from flask_restplus import Api, Resource, fields, reqparse

from .server import GetGeometry
from .server import GetCities
from .server import GetCity
from .server import GetAttribute
from .server import GetTile
from .server import GetScene

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
class APIGetGeometry(Resource):

    @api.expect(getgeom_parser, validate=True)
    def get(self):
        args = getgeom_parser.parse_args()
        return GetGeometry().run(args)


# getCities
@api.route("/getCities")
class APIGetCities(Resource):

    def get(self):
        return GetCities().run()


# getCity
getcity_parser = reqparse.RequestParser()
getcity_parser.add_argument('city', type=str, required=True)


@api.route("/getCity")
class APIGetCity(Resource):

    @api.expect(getcity_parser, validate=True)
    def get(self):
        args = getcity_parser.parse_args()
        return GetCity().run(args)


# getAttribute
getattr_parser = reqparse.RequestParser()
getattr_parser.add_argument('city', type=str, required=True)
getattr_parser.add_argument('gid', type=str, required=True)
getattr_parser.add_argument('attribute', type=str, required=True)


@api.route("/getAttribute")
class APIGetAttribute(Resource):

    @api.expect(getattr_parser, validate=True)
    def get(self):
        args = getattr_parser.parse_args()
        return GetAttribute().run(args)

# getTile
gettile_parser = reqparse.RequestParser()
gettile_parser.add_argument('city', type=str, required=True)
gettile_parser.add_argument('layer', type=str, required=True)
gettile_parser.add_argument('tile', type=int, required=True)
gettile_parser.add_argument('depth', type=int, required=True)
gettile_parser.add_argument('representation', type=str, required=True)
@api.route("/getTile")
class APIGetTile(Resource):

    @api.expect(gettile_parser, validate=True)
    def get(self):
        args = gettile_parser.parse_args()
        return GetTile().run(args)

# getScene
getscene_parser = reqparse.RequestParser()
getscene_parser.add_argument('city', type=str, required=True)
getscene_parser.add_argument('layer', type=str, required=True)
getscene_parser.add_argument('representations', type=str, required=True)
getscene_parser.add_argument('weights', type=str, required=True)
getscene_parser.add_argument('maxdepth', type=int, required=False)
getscene_parser.add_argument('tile', type=int, required=False)
getscene_parser.add_argument('depth', type=int, required=False)
# TODO: customisation parameters
@api.route("/getScene")
class APIGetScene(Resource):

    @api.expect(getscene_parser, validate=True)
    def get(self):
        args = getscene_parser.parse_args()
        return GetScene().run(args)
