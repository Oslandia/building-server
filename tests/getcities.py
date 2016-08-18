# -*- coding: utf-8 -*-

import unittest
import json
import os

from building_server.utils import CitiesConfig
from building_server.server import GetCities


class TestGetCities(unittest.TestCase):

    def setUp(self):
        cfgfile = ("{0}/testcfg.yml"
                   .format(os.path.dirname(os.path.abspath(__file__))))
        CitiesConfig.init(cfgfile)

    def tearDown(self):
        pass

    def test(self):
        # expected json
        # {"montreal": {"featurespertile": 2,
        # "maxtilesize": 2000, "tablename": "montreal",
        # "srs": "EPSG:2950",
        # "extent": [[297949.75, 5040582.5],
        # [299337.78, 5042223.5]], "attributes": []}}

        str_result = GetCities().run()
        json_result = json.loads(str_result)["montreal"]

        self.assertEqual(json_result["srs"], "EPSG:2950")
        self.assertEqual(json_result["featurespertile"], 2)
        self.assertEqual(json_result["maxtilesize"], 2000)
        self.assertEqual(json_result["tablename"], "montreal")
        self.assertEqual(json_result["extent"],
                         [[297949.75, 5040582.5], [299337.78, 5042223.5]])
        self.assertEqual(json_result["attributes"], [])
