#!/usr/bin/env python
# -*- coding: utf-8 -*-

import struct
from flask import Response
from . import utils
from .database import Session
from .utils import CitiesConfig
from py3dtiles import GlTF, B3dm
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
        if args.get('attributes'):
            attributes = args['attributes'].split(',')

        # get geometries for a specific tile in database
        geomsjson = Session.tile_geom_geojson(city, [0,0,0], tile)

        # build a features collection with extra properties if necessary
        feature_collection = utils.FeatureCollection()
        if utils.CitiesConfig.cities.get(city):
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
            for geom in geombin:
                wkbs.append(geom['geom'])
                box = utils.Box3D(geom['box'])
                boxes.append(box.asarray())
            if args['triangles']:
                gltf = GlTF.from_wkb_as_triangles(wkbs, boxes, transform)
            else:
                gltf = GlTF.from_wkb_as_lines(wkbs, boxes, transform)

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
        lvl0Tiles = Session.tiles_for_level(city, 0)

        lvl0Nodes = []
        for tile in lvl0Tiles:
            node = {
                'box': utils.Box3D(tile['bbox']),
                'id': tile['quadtile'],
                'depth': 0,
                'children': []
            }
            lvl0Nodes.append(node)

        if len(lvl0Tiles) == 1:
            root = lvl0Nodes[0]
        else:
            pmin = [float("inf"), float("inf"), float("inf")]
            pmax = [-float("inf"), -float("inf"), -float("inf")]
            for n in lvl0Nodes:
                corners = n['box'].corners()
                pmin = [min(pmin[i], corners[0][i]) for i in range(0,3)]
                pmax = [max(pmax[i], corners[1][i]) for i in range(0,3)]
            box = 'Box3D({0},{1},{2},{3},{4},{5})'.format(*(pmin+pmax))
            box = utils.Box3D(box)
            root = {
                'box': box,
                'depth': 0,
                'children': lvl0Nodes
            }

        hierarchy = {}
        for tile in tiles:
            hierarchy[tile['quadtile']] = tile['bbox']

        nodeQueue = []
        nodeQueue = nodeQueue + lvl0Nodes
        while len(nodeQueue) != 0:
            parent = nodeQueue.pop(0)
            id = parent['id']
            [z, y, x] = map(int, id.split("/"))
            ids = [str(z+1) + "/" + str(2*y) + "/" + str(2*x),
                   str(z+1) + "/" + str(2*y+1) + "/" + str(2*x),
                   str(z+1) + "/" + str(2*y) + "/" + str(2*x+1),
                   str(z+1) + "/" + str(2*y+1) + "/" + str(2*x+1)]

            for t in ids:
                if t in hierarchy:
                    node = {
                        'box': utils.Box3D(hierarchy[t]),
                        'id': t,
                        'depth': z + 1,
                        'children': []
                    }
                    parent['children'].append(node)
                    nodeQueue.append(node)


        resp = Response(self._to_3dtiles(root, city, dataFormat))
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'text/plain'
        return resp


    def _compute_tile_geometric_error(self, node, city):
        error = 0
        for n in node['children']:
            error += Session.tile_geom_score(city, n['id'])
        return error

    def _to_3dtiles(self, root, city, dataFormat):
        tiles = {
            "asset": {"version" : "1.0", "gltfUpAxis": "Z"},
            "geometricError": self._compute_tile_geometric_error(root, city),
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
            "geometricError": self._compute_tile_geometric_error(node, city),
            "children": [self._to_3dtiles_r(n, city, dataFormat) for n in node['children']],
            "refine": "add"
        }
        if 'id' in node:
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
