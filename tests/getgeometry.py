# -*- coding: utf-8 -*-

import unittest
import json
from building_server.database import Session
from building_server.server import GetGeometry


class MockSession(object):

    def offset(self, city, tile):
        return [298814.346516, 5041264.75924, 43.595718]

    def tile_geom_geojson(self, city, offset, tile):
        d0 = {}
        d0['gid'] = 1795
        d0['geom'] = ('{"type":"PolyhedralSurface",'
                      '"bbox":[0.00,0.00,0.00,56.49,46.03,0.00],'
                      '"coordinates":[[[[52.58,9.96,0],[44.15,1.24,0],'
                      '[32.76,7.78,0],[52.58,9.96,0]]],[[[56.49,15.91,0],'
                      '[54.04,12.19,0],[56.37,15.99,0],[56.49,15.91,0]]]]}')

        d1 = {}
        d1['gid'] = 1796
        d1['geom'] = ('{"type":"PolyhedralSurface",'
                      '"bbox":[1.00,0.00,0.00,56.49,46.03,0.00],'
                      '"coordinates":[[[[53.58,9.96,0],[44.15,1.24,0],'
                      '[32.76,7.78,0],[52.58,9.96,0]]],[[[56.49,15.91,0],'
                      '[54.04,12.19,0],[56.37,15.99,0],[56.49,15.91,0]]]]}')

        return [d0, d1]

    def bbox_for_quadtiles(self, city, quadtiles):
        d0 = {}
        d0['quadtile'] = "6/22/28"
        d0['bbox'] = ('BOX3D(298814.346516 5041264.75924 43.595718,'
                      '298870.831717 5041310.79423 43.595718)')

        d1 = {}
        d1['quadtile'] = "8/58/131"
        d1['bbox'] = ('BOX3D(298965.878429 5041026.69609 43.23579,'
                      '298980.783748 5041048.36555 59.574652)')

        return [d0, d1]

    def attribute_for_gid(self, city, gid, attribute):

        if gid == "1795":
            if attribute == "weight":
                return "131.418"
            elif attribute == "quadtile":
                return "6/22/28"
        elif gid == "1796":
            if attribute == "weight":
                return "509.653"
            elif attribute == "quadtile":
                return "8/58/131"

    def empty_tile_geom_binary(self, city, tile):
        return []


class TestGetGeometry(unittest.TestCase):

    def setUp(self):
        # init mock session
        self.mockSession = MockSession()
        Session.offset = self.mockSession.offset
        Session.tile_geom_geojson = self.mockSession.tile_geom_geojson
        Session.bbox_for_quadtiles = self.mockSession.bbox_for_quadtiles
        Session.attribute_for_gid = self.mockSession.attribute_for_gid

        # build args
        self.args = {}
        self.args['city'] = "montreal"
        self.args['tile'] = "6/22/28"
        self.args['attributes'] = ""

    def tearDown(self):
        pass

    def test_format_geojson(self):
        # expected json format
        # {"geometries":{"type": "FeatureCollection",
        # "crs":{"type":"name","properties":{"name":"EPSG:3946"}},
        # "fs": [
        # {"type":"Feature", "id": "lyongeom.1795",
        # "properties":{"gid": "1795"},
        # "geometry": {"type":"PolyhedralSurface",
        # "bbox":[0.00,0.00,0.00,56.49,46.03,0.00],
        # "coordinates":[[[[52.58,9.96,0],...,[44.32,26.15,0]]]]}},
        # {"type":"Feature", "id": "lyongeom.1795",
        # "properties":{"gid": "1796"},
        # "geometry": {"type":"PolyhedralSurface",
        # "bbox":[0.00,0.00,0.00,57.49,46.03,0.00],
        # "coordinates":[[[[53.58,9.96,0],...,[44.32,26.15,0]]]]}},
        # ]},
        # "tiles":[{"id":"6/22/28",
        # "bbox":[298814.346516,5041264.75924,43.595718,298870.831717,
        # 5041310.79423,43.595718]},
        # {"id":"8/58/131","bbox":[298965.878429,5041026.69609,
        # 43.23579,298980.783748,5041048.36555,59.574652]}]}

        args = self.args
        args['format'] = "geojson"

        result = GetGeometry().run(args)
        json_result = json.loads(result)

        json_geom = json_result["geometries"]
        self.assertEqual(json_geom["type"], "FeatureCollection")

        json_fs = json_geom["features"]
        json_f0 = json_fs[0]
        json_f1 = json_fs[1]

        self.assertEqual(json_f0["id"], "lyongeom.1795")
        self.assertEqual(json_f1["id"], "lyongeom.1796")

        self.assertEqual(json_f0["properties"]["gid"], "1795")
        self.assertEqual(json_f1["properties"]["gid"], "1796")

        json_f0_geom = json_f0["geometry"]
        json_f1_geom = json_f1["geometry"]

        self.assertEqual(json_f0_geom["type"], "PolyhedralSurface")
        self.assertEqual(json_f1_geom["type"], "PolyhedralSurface")

        self.assertEqual(json_f0_geom["bbox"],
                         [0.00, 0.00, 0.00, 56.49, 46.03, 0.00])
        self.assertEqual(json_f1_geom["bbox"],
                         [1.00, 0.00, 0.00, 56.49, 46.03, 0.00])

        self.assertEqual(json_f0_geom["coordinates"], [[[[52.58, 9.96, 0],
                         [44.15, 1.24, 0], [32.76, 7.78, 0],
                         [52.58, 9.96, 0]]], [[[56.49, 15.91, 0],
                         [54.04, 12.19, 0], [56.37, 15.99, 0],
                         [56.49, 15.91, 0]]]])
        self.assertEqual(json_f1_geom["coordinates"], [[[[53.58, 9.96, 0],
                         [44.15, 1.24, 0], [32.76, 7.78, 0],
                         [52.58, 9.96, 0]]], [[[56.49, 15.91, 0],
                         [54.04, 12.19, 0], [56.37, 15.99, 0],
                         [56.49, 15.91, 0]]]])

        json_tile0 = json_result["tiles"][0]
        json_tile1 = json_result["tiles"][1]

        self.assertEqual(json_tile0["id"], "6/22/28")
        self.assertEqual(json_tile1["id"], "8/58/131")

        self.assertEqual(json_tile0["bbox"], [298814.346516, 5041264.75924,
                         43.595718, 298870.831717, 5041310.79423, 43.595718])
        self.assertEqual(json_tile1["bbox"], [298965.878429, 5041026.69609,
                         43.23579, 298980.783748, 5041048.36555, 59.574652])

    def test_format_empty_binary(self):
        # 'glTF\x01\x00\x00\x00\x14\x00\x00\x00\x00\x00\x00\x00\x00\x00
        # \x00\x00{"tiles":[]}'
        expected = bytearray(b'\x67\x6c\x54\x46\x01\x00\x00\x00\x14\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x7b\x22\x74\x69\x6c\x65\x73\x22\x3a\x5b\x5d\x7d')

        Session.tile_geom_binary = self.mockSession.empty_tile_geom_binary

        args = self.args
        args['format'] = ""

        result = GetGeometry().run(args)
        self.assertEqual(result, expected.decode("utf-8"))


    def test_with_attribute(self):
        # expected json format
        # ... "features": [{"type":"Feature", "id": "lyongeom.1795",
        # "properties":{"gid": "1795","weight": "2600.3",
        # "quadtile": "6/22/28"},

        args = self.args
        args['format'] = "geojson"
        args['attributes'] = "quadtile,weight"

        result = GetGeometry().run(args)
        json_result = json.loads(result)

        json_f0_prop = json_result["geometries"]["features"][0]["properties"]
        json_f1_prop = json_result["geometries"]["features"][1]["properties"]

        self.assertEqual(json_f0_prop["gid"], "1795")
        self.assertEqual(json_f1_prop["gid"], "1796")

        self.assertEqual(json_f0_prop["weight"], "131.418")
        self.assertEqual(json_f1_prop["weight"], "509.653")

        self.assertEqual(json_f0_prop["quadtile"], "6/22/28")
        self.assertEqual(json_f1_prop["quadtile"], "8/58/131")
