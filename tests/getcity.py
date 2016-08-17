# -*- coding: utf-8 -*-

import unittest
import json
from building_server.database import Session
from building_server.server import GetCity


class MockSession(object):

    def tiles_for_level(self, city, level):
        d0 = {}
        d0['quadtile'] = '6/22/28'
        d0['bbox'] = ('BOX3D(298814.346516 5041264.75924 '
                      '43.595718,298870.831717 5041310.79423 43.595718)')

        d1 = {}
        d1['quadtile'] = '8/58/131'
        d1['bbox'] = ('BOX3D(298965.878429 5041026.69609 43.23579,'
                      '298980.783748 5041048.36555 59.574652)')

        return [d0, d1]


class TestGetCity(unittest.TestCase):

    def setUp(self):
        # init mock session
        mockSession = MockSession()
        Session.tiles_for_level = mockSession.tiles_for_level

        # build args
        self.args = {}
        self.args['city'] = "montreal"

    def tearDown(self):
        pass

    def test(self):
        # expected json
        # {"tiles":[
        # {"id":"6/22/28","bbox":[298814.346516,
        # 5041264.75924,43.595718,298870.831717,
        # 5041310.79423,43.595718]},
        # {"id":"8/58/131","bbox":[298965.878429,
        # 5041026.69609,43.23579,298980.783748,
        # 5041048.36555,59.574652]}]}

        result = GetCity().run(self.args)
        json_result = json.loads(result)

        json_tile0 = json_result["tiles"][0]
        self.assertEqual(json_tile0["id"], "6/22/28")
        self.assertEqual(json_tile0["bbox"],
                         [298814.346516, 5041264.75924, 43.595718,
                         298870.831717, 5041310.79423, 43.595718])

        json_tile1 = json_result["tiles"][1]
        self.assertEqual(json_tile1["id"], "8/58/131")
        self.assertEqual(json_tile1["bbox"],
                         [298965.878429, 5041026.69609, 43.23579,
                         298980.783748, 5041048.36555, 59.574652])
