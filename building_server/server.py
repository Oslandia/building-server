#!/usr/bin/env python
# -*- coding: utf-8 -*-

import struct
from . import utils
from . import settings
from .database import Session
from .transcode import toglTF


class GetGeometry(object):

    def run(self, args):
        outputFormat = args['format']

        geometry = ""
        if outputFormat:
            if outputFormat.lower() == "geojson":
                geometry = self._as_geojson(args)
            else:
                geometry = self._as_binary(args)
        else:
            geometry = self._as_binary(args)

        return geometry

    def _as_geojson(self, args):

        # arguments
        city = args['city']
        tile = args['tile']
        attributes = []
        if args['attributes']:
            attributes = args['attributes'].split(',')

        # get offset in database
        offset = Session.offset(city, tile)

        # get geometries for a specific tile in database
        geomsjson = Session.tile_geom_geojson(city, offset, tile)

        # build a features collection with extra properties if necessary
        feature_collection = utils.FeatureCollection()

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

        # build children bboxes
        bboxes_str = self._children_bboxes(city, tile)

        # build the resulting json
        geometries = utils.Property("geometries", feature_collection.geojson())
        json = ('{{ {0}, "tiles":[{1}]}}'
                .format(geometries.geojson(), bboxes_str))

        return json

    def _as_binary(self, args):
        # retrieve arguments
        city = args['city']
        tile = args['tile']

        # get geom as binary
        geombin = Session.tile_geom_binary(city, tile)

        json = ""
        if not geombin:
            json = struct.pack('4sIIII', b"glTF", 1, 20, 0, 0)  # empty bglTF
            json += b'{"tiles":[]}'
            json = json.decode("utf-8")
        else:
            offset = Session.offset(city, tile)

            # prepare data for toglTF function and run it
            data = []
            for geom in geombin:
                data.append((geom['binary'], geom['box3d']))
            json = toglTF(data, True, offset)

            # build children bboxes
            bboxes_str = self._children_bboxes(city, tile)

            # build the resulting json
            json = ('{0}, "tiles":[{1}]}}'
                    .format(json, bboxes_str))

        return json

    def _children_bboxes(self, city, tile):

        [z, y, x] = map(int, tile.split("/"))
        q0 = str(z+1) + "/" + str(2*y) + "/" + str(2*x)
        q1 = str(z+1) + "/" + str(2*y+1) + "/" + str(2*x)
        q2 = str(z+1) + "/" + str(2*y) + "/" + str(2*x+1)
        q3 = str(z+1) + "/" + str(2*y+1) + "/" + str(2*x+1)

        bboxs = Session.bbox_for_quadtiles(city, [q0, q1, q2, q3])
        lbb = []
        for bbox in bboxs:
            b = utils.Box3D(bbox['bbox'])
            qstr = ('{{"id" : "{0}", {1}}}'
                    .format(bbox['quadtile'], b.geojson()))
            lbb.append(qstr)

        bboxes_str = ', '.join(lbb)

        return bboxes_str


class GetCities(object):

    def run(self):
        return str(settings.CITIES).replace('\'', '"')


class GetCity(object):

    def run(self, args):
        city = args['city']
        tiles = Session.tiles_for_level(city, 0)

        json = ""
        for tile in tiles:
            b = utils.Box3D(tile['bbox'])
            p = utils.Property("id", '"{0}"'.format(tile['quadtile']))

            tilejson = ('{{ {0}, {1} }}'
                        .format(p.geojson(), b.geojson()))
            if json:
                json = "{0}, {1}".format(json, tilejson)
            else:
                json = tilejson
        json = '{{"tiles":[{0}]}}'.format(json)

        return json


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
        return json
