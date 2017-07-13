#!/usr/bin/env python
# -*- coding: utf-8 -*-

import struct
from flask import Response
from . import utils
from .database import Session
from .utils import CitiesConfig
from py3dtiles import GlTF, B3dm, TriangleSoup
import json
import numpy as np


class GetGeometry(object):

    def run(self, args):
        outputFormat = args['format']

        geometry = ""
        if outputFormat:
            if outputFormat.lower() == "geojson":
                geometry = self._as_geojson(args)
                contentType = 'text/plain'
            else:
                geometry = self._as_b3dm(args)
                contentType = 'application/octet-stream'
        else:
            geometry = self._as_b3dm(args)
            contentType = 'application/octet-stream'

        resp = Response(geometry)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = contentType

        return resp

    def _as_geojson(self, args):

        # arguments
        city = args['city']
        tile = args['tile']
        attributes = []
        if args['attributes']:
            attributes = args['attributes'].split(',')

        # get geometries for a specific tile in database
        geomsjson = Session.tile_geom_geojson(city, [0,0,0], tile)

        # build a features collection with extra properties if necessary
        feature_collection = utils.FeatureCollection()
        feature_collection.srs = utils.CitiesConfig.cities[city]['srs']

        for geom in geomsjson:
            properties = utils.PropertyCollection()
            property = utils.Property('gid', '"{0}"'.format(geom['gid']))
            properties.add(property)

            for attribute in attributes:
                val = Session.attribute_for_gid(city, str(geom['gid']),
                                                attribute)
                property = utils.Property(attribute, '"{0}"'.format(val))
                properties.add(property)

            f = utils.Feature(geom['gid'], properties, geom['geom'])
            feature_collection.add(f)

        return feature_collection.geojson()

    def _as_b3dm(self, args):
        # retrieve arguments
        city = args['city']
        tile = args['tile']

        # get geom as binary
        offset = Session.offset(city, tile)
        geombin = Session.tile_geom_binary(city, tile, offset)

        output = ""
        if not geombin:
            gltf = struct.pack('4sIIII', b"glTF", 1, 20, 0, 0)  # empty bglTF
            gltf += b'{"tiles":[]}'
        else:
            wkbs = []
            boxes = []
            transform = np.array([
                [1,0,0,offset[0]],
                [0,1,0,offset[1]],
                [0,0,1,offset[2]],
                [0,0,0,1]], dtype=float)
            transform = transform.flatten('F')
            geometries = []
            for geom in geombin:
                ts = TriangleSoup.from_wkb_multipolygon(geom['geom'])
                geometries.append({
                    'position': ts.getPositionArray(),
                    'normal': ts.getNormalArray(),
                    'bbox': utils.Box3D(geom['box']).asarray()
                })
            gltf = GlTF.from_binary_arrays(geometries, transform)

        b3dm = B3dm.from_glTF(gltf).to_array().tostring()

        return b3dm


class GetCities(object):

    def run(self):
        cities_str = str(CitiesConfig.cities).replace('\'', '"')

        resp = Response(cities_str)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'text/plain'

        return resp


class GetCity(object):

    def run(self, args):
        city = args['city']
        if 'format' in args:
            dataFormat = args['format']
        else:
            dataFormat = 'b3dm'

        tiles = Session.get_all_tiles(city)
        hierarchy_tuples = Session.get_hierarchy(city)

        hierarchy = {}
        for t in hierarchy_tuples:
            tile = t['tile']
            child = t['child']
            if tile not in hierarchy:
                hierarchy[tile] = []
            hierarchy[tile].append(child)

        bboxIndex = {}
        for t in tiles:
            bboxIndex[t['tile']] = t['bbox']

        root = {
            'box': utils.Box3D(bboxIndex[0]),
            'id': 0,
            'depth': 0,
            'children': []
        }
        nodeQueue = [root]
        while len(nodeQueue) != 0:
            parent = nodeQueue.pop(0)
            id = parent['id']
            depth = parent['depth']

            if id in hierarchy:
                for childId in hierarchy[id]:
                    node = {
                        'box': utils.Box3D(bboxIndex[childId]),
                        'id': childId,
                        'depth': depth + 1,
                        'children': []
                    }
                    parent['children'].append(node)
                    nodeQueue.append(node)


        resp = Response(self._to_3dtiles(root, city, dataFormat))
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'text/plain'
        return resp

    def _to_3dtiles(self, root, city, dataFormat):
        tiles = {
            "asset": {"version" : "1.0", "gltfUpAxis": "Z"},
            "geometricError": 500, # TODO
            "root" : self._to_3dtiles_r(root, city, dataFormat)
        }
        return json.dumps(tiles)

    def _to_3dtiles_r(self, node, city, dataFormat):
        (c1, c2) = node['box'].corners()
        center = [(c1[i] + c2[i]) / 2 for i in range(0,3)]
        xAxis = [c2[0] - c1[0], 0, 0]
        yAxis = [0, c2[1] - c1[1], 0]
        zAxis = [0, 0, c2[2] - c1[2]]
        box = center + xAxis + yAxis + zAxis
        tile = {
            "boundingVolume": {
                "box": box
            },
            "geometricError": 500 / (node['depth'] + 1), # TODO
            "children": [self._to_3dtiles_r(n, city, dataFormat) for n in node['children']],
            "refine": "add"
        }
        if node['id'] != 0:
            tile["content"] = {
                "url": "getGeometry?city={0}&tile={1}&format={2}".format(city, node['id'], dataFormat)
            }

        return tile


class GetAttribute(object):

    def run(self, args):
        city = args['city']
        gids = args['gid'].split(',')
        attributes = args['attribute'].split(',')

        json = ""
        for gid in gids:
            gidjson = ""
            for attribute in attributes:
                val = Session.attribute_for_gid(city, str(gid), attribute)
                property = utils.Property(attribute, '"{0}"'.format(val))
                if gidjson:
                    gidjson = "{0}, {1}".format(gidjson, property.geojson())
                else:
                    gidjson = property.geojson()
            gidjson = "{{ {0} }}".format(gidjson)

            if json:
                json = "{0}, {1}".format(json, gidjson)
            else:
                json = gidjson

        json = "[{0}]".format(json)

        resp = Response(json)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'text/plain'

        return resp
