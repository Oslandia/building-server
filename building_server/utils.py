# -*- coding: utf-8 -*-

import io
import yaml


class CitiesConfig(object):

    cities = {}

    @classmethod
    def init(cls, cfgfile):
        content = io.open(cfgfile, 'r').read()
        cls.cities = yaml.load(content).get('cities', {})

    @classmethod
    def table(cls, city):
        if city in cls.cities:
            return cls.cities[city]['tablename']
        else:
            return city


class Box3D(object):

    def __init__(self, str):
        self.str = str

    def aslist(self, bracket=True):
        if bracket:
            return "[" + self.str[6:len(self.str)-1].replace(" ", ",") + "]"
        else:
            return self.str[6:len(self.str)-1].replace(" ", ",")

    def centroid(self):
        [p1, p2] = self.corners()
        centroid = ((p2[0] + p1[0]) / 2., (p2[1] + p1[1]) / 2.)
        return centroid

    def corners(self):
        box = self.aslist(bracket=False).split(",")
        c1 = [float(box[0]), float(box[1]), float(box[2])]
        c2 = [float(box[3]), float(box[4]), float(box[5])]
        return [c1, c2]

    def geojson(self):
        p = Property("bbox", self.aslist())
        return p.geojson()

    def asarray(self):
        return [[float(n) for n in s.split(" ")] for s in self.str[6:len(self.str)-1].split(",")]

class Property(object):

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def geojson(self):
        return '"{0}" : {1}'.format(self.name, self.value)


class PropertyCollection(object):

    def __init__(self):
        self.properties = []

    def add(self, property):
        self.properties.append(property)

    def geojson(self):
        json = ""

        for property in self.properties:
            if json:
                json = "{0}, {1}".format(json, property.geojson())
            else:
                json = property.geojson()

        json = '"properties" : {{{0}}}'.format(json)

        return json


class Feature(object):

    def __init__(self, id, properties, geometry):
        self.id = id
        self.properties = properties
        self.geometry = geometry

    def geojson(self):
        json = ('{{ {0}, {1}, {2}, {3} }}'
                .format(self._geojson_type(), self._geojson_id(),
                        self._geojson_properties(), self._geojson_geometry()))
        return json

    def _geojson_type(self):
        return '"type" : "Feature"'

    def _geojson_id(self):
        return '"id" : "lyongeom.{0}"'.format(self.id)

    def _geojson_properties(self):
        return self.properties.geojson()

    def _geojson_geometry(self):
        return '"geometry" : {0}'.format(self.geometry)


class FeatureCollection(object):

    def __init__(self):
        self.features = []
        self.srs = "EPSG:3946"

    def add(self, feature):
        self.features.append(feature)

    def geojson(self):
        json = ('{{ {0}, {1}, {2} }}'
                .format(self._geojson_type(), self._geojson_crs(),
                        self._geojson_features()))
        return json

    def _geojson_type(self):
        return '"type" : "FeatureCollection"'

    def _geojson_crs(self):
        json = ('"crs" : {{ "type" : "name",'
                '"properties" : {{"name" : "{0}"}}}}'
                .format(self.srs))
        return json

    def _geojson_features(self):
        json = ""

        for feature in self.features:
            if json:
                json = "{0}, {1}".format(json, feature.geojson())
            else:
                json = feature.geojson()

        json = '"features" : [{0}]'.format(json)

        return json
