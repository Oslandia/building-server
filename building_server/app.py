# -*- coding: utf-8 -*-
from flask import request
from flask_restplus import Api, Resource, fields, reqparse

api = Api(
        version='0.1', title='Building Server API',
        description='API for accessing Building Server',
        )

# -----------------------------------------------------------------------------
# basic api
# -----------------------------------------------------------------------------
@api.route("/building_server")
class Test(Resource):

    def get(self):
        return "Building Server / Oslandia / contact@oslandia.com"
