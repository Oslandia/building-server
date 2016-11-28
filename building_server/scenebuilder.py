#!/usr/bin/env python
# -*- coding: utf-8 -*-

#import psycopg2
#import math
#import pprint
#import time
#import sys
#import settings
import json
from . import utils

class Node(object):

    def __init__(self, id, representation, weight, box):
        self.id = id
        self.representation = representation
        self.weight = weight
        self.children = []
        self.parent = None
        self.combinees = []
        self.box = box

    def __str__(self):
        return "Node " + self.id + ", " + str(self.representation) + ", " + str(self.weight)

    def remove(self, child):
        self.children.remove(child)
        child.parent = None

    def add(self, child):
        self.children.append(child)
        child.parent = self

def walk(node):
    yield node
    for child in node.children:
        for n in walk(child):
            yield n

class SceneBuilder():

    @classmethod
    def build(cls, cursor, city, layer, representations):
        tileTable = utils.CitiesConfig.tileTable(city)
        tileHierarchy = utils.CitiesConfig.tileHierarchy(city)

        reps = []
        for i in range(0, len(representations)):
            r = utils.CitiesConfig.representation(city, layer, representations[i][0])
            r["name"] = representations[i][0]
            r["weight"] = representations[i][1]
            reps.append(r)

        reps = sorted(reps,  key=lambda e: e["detail"])

        # Calculer le score de chaque représentation
        nodes = {}
        lvl0Nodes = []
        query = "SELECT tile, depth, bbox FROM {0}".format(tileTable)
        cursor.execute(query)
        rows = cursor.fetchall()
        for r in rows:
            depth = r[1]
            if r[2] != None:
                box = utils.Box3D(r[2])

            # Go through every representations in order of increasing detail
            existingRepresentations = []
            for rep in reps:
                query = "SELECT tile FROM {0} WHERE tile='{1}'".format(rep['tablename'], r[0])
                cursor.execute(query)
                if cursor.rowcount != 0:
                    score = (1 + depth) * rep['weight'] #TODO: Temp
                    existingRepresentations.append((rep["name"], score, box))

            # Linking node's representations
            nodeRep = []
            for i, rep in enumerate(existingRepresentations):
                node = Node(r[0], rep[0], rep[1], rep[2]);
                nodeRep.append(node)
                if depth == 0 and i == 0:
                    lvl0Nodes.append(node)
                if i != 0:
                    nodeRep[0].children.append(node)
                    node.parent = nodeRep[0]
            nodes[r[0]] = nodeRep


        # Linking nodes
        query = "SELECT tile, child FROM {0}".format(tileHierarchy)
        cursor.execute(query)
        rows = cursor.fetchall()
        for r in rows:
            if(len(nodes[r[0]]) != 0 and len(nodes[r[1]]) != 0):
                nodes[r[0]][-1].add(nodes[r[1]][0])

        # Parcours hierarchie
        if len(lvl0Nodes) == 1:
            root = lvl0Nodes[0]
        else:
            root = Node(-1, "None", 0)
            root.children = lvl0Nodes

        cls.pushUp(root)

        return cls.to3dTiles(root, city, layer)

    @classmethod
    def pushUp(cls, root):
        toRemove = []
        toCombine = {}
        for n in walk(root):
            highestNode = cls.findHighestNode(n.weight, n)
            if highestNode != n:
                if highestNode not in toCombine:
                    toCombine[highestNode] = []
                toCombine[highestNode].append(n)
                toRemove.append(n)
            n.leaf = (len(n.children) == 0)

        for n in toRemove:
            parent = n.parent
            n.parent.remove(n)


        for n in toCombine:
            if len(n.children) == 0:
                # Replace
                for combiners in toCombine[n]:
                    n.parent.add(combiners)
                n.parent.remove(n)
            else:
                # Combine
                for combiners in toCombine[n]:
                    n.combinees.append(combiners)

    @classmethod
    def findHighestNode(cls, w, node):
        if node.parent == None:
                return node
        if node.parent.weight >= w:
            return cls.findHighestNode(w, node.parent)
        else:
            return node

    @classmethod
    def to3dTiles(cls, root, city, layer):
        tiles = {
            "asset": {"version" : "1.0"},
            "geometricError": 500,
            "root" : cls.to3dTiles_r(root, city, layer)
        }
        return json.dumps(tiles)

    @classmethod
    def to3dTiles_r(cls, node, city, layer):
        # TODO : handle combined nodes
        (c1, c2) = node.box.corners()
        center = [(c1[i] + c2[i]) / 2 for i in range(0,3)]
        xAxis = [c2[0] - c1[0], 0, 0]
        yAxis = [0, c2[1] - c1[1], 0]
        zAxis = [0, 0, c2[2] - c1[2]]
        box = center + xAxis + yAxis + zAxis
        tile = {
            "boundingVolume": {
                "box": box
            },
            "content": {
                "url": "getTile?city={0}&layer={1}&tile={2}&representation={3}".format(city, layer, node.id, node.representation)
            },
            "geometricError": 100 / node.weight, # TODO
            "children": [cls.to3dTiles_r(n, city, layer) for n in node.children]
        }
        return tile

"""
if __name__ == '__main__':
    args = sys.argv;
    if len(args) <= 1:
        exit("No city name provided")

    cityName = args[1];
    if cityName not in settings.CITIES:
        exit("City " + cityName + " is not defined in settings.py")

    city = settings.CITIES[cityName]
    if "tablename" not in city or "extent" not in city or "maxtilesize" not in city:
        exit(cityName + " not properly defined")



    conn_string = "host='%s' dbname='%s' user='%s' password='%s' port='%s'" % (settings.DB_INFOS['host'], settings.DB_INFOS['dbname'], settings.DB_INFOS['user'], settings.DB_INFOS['password'], settings.DB_INFOS['port'])
    connection = psycopg2.connect(conn_string)
    cursor = connection.cursor()

    initDB(cursor, city)
    connection.commit()
    cursor.close()
    connection.close()
"""
