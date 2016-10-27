# -*- coding: utf-8 -*-

import unittest
import json
from building_server.database import Session
from building_server.server import GetAttribute


class MockSession(object):

    def attribute_for_gid(self, city, gid, attribute):

        if gid == "1":
            if attribute == "weight":
                return "131.418"
            elif attribute == "quadtile":
                return "5/15/12"
        elif gid == "200":
            if attribute == "weight":
                return "509.653"
            elif attribute == "quadtile":
                return "6/7/33"


class TestGetAttribute(unittest.TestCase):

    def setUp(self):
        # init mock session
        mockSession = MockSession()
        Session.attribute_for_gid = mockSession.attribute_for_gid

        # build args
        self.args = {}
        self.args['city'] = "montreal"
        self.args['gid'] = "1,200"
        self.args['attribute'] = "weight,quadtile"

    def tearDown(self):
        pass

    def test(self):
        # expected json
        # [{"weight":131.418,"quadtile":5/15/12},
        # {"weight":509.653,"quadtile":6/7/33}]

        result = GetAttribute().run(self.args)
        json_result = json.loads(result)

        json_gid0 = json_result[0]
        self.assertEqual(json_gid0["weight"], "131.418")
        self.assertEqual(json_gid0["quadtile"], "5/15/12")

        json_gid1 = json_result[1]
        self.assertEqual(json_gid1["weight"], "509.653")
        self.assertEqual(json_gid1["quadtile"], "6/7/33")
