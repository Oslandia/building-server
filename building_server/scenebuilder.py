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
from psycopg2 import sql

class RuleEngine(object):

    def __init__(self, ruleset):
        #parse(ruleset)
        self.default = {
            0: ["lod1"],
            1: ["lod1"],
            #2: ["lod1"],
            #3: ["lod1"]
        }
        self.tileConditions = [
            (
                {
                    'type': "zone",
                    'center': [1844040, 5175290], # Part-dieu
                    'radius': 500
                },
                {
                    #2: ["lod1"],
                    3: ["lod1"]
                }
            )
        ]
        self.featureConditions = [
            (
                {
                    'type': "greater",
                    'attribute': "height",
                    'value': "50"
                },
                {
                    1: ["lod2"]
                }
            )
        ]
        self.tileIndex = {}
        self.tileFeatureIndex = {}

    def testTiles(self, cursor, city, layer):
        srid = 3946 # TODO: get from config file
        tileTable = utils.CitiesConfig.tileTable(city)
        for tc in self.tileConditions:
            condition = tc[0]
            action = tc[1]
            if condition['type'] == "zone":
                cursor.execute(
                    sql.SQL("SELECT tile FROM {} WHERE ST_Intersects(footprint, ST_Buffer(ST_GeomFromText('POINT(%s %s)', %s), %s))")
                        .format(sql.SQL('.').join([sql.Identifier(a) for a in tileTable.split('.')])),
                    [condition['center'][0], condition['center'][1], srid, condition['radius']]
                )
            for t in cursor.fetchall():
                if t[0] not in self.tileIndex:
                    self.tileIndex[t[0]] = action


    def testFeatures(self, cursor, city, layer):
        srid = 3946 # TODO: get from config file
        featureTable = utils.CitiesConfig.featureTable(city, layer)
        featureSet = set()
        for fc in self.featureConditions:
            condition = fc[0]
            action = fc[1]
            if condition['type'] == "greater":
                cursor.execute(
                    sql.SQL("SELECT gid, tile FROM {} WHERE {}>%s")
                        .format(sql.SQL('.').join([sql.Identifier(a) for a in featureTable.split('.')]), sql.Identifier(condition['attribute'])),
                    [float(condition['value'])]
                )
            for t in cursor.fetchall():
                if t[0] not in featureSet:
                    featureSet.add(t[0])
                    if t[1] not in self.tileFeatureIndex:
                        self.tileFeatureIndex[t[1]] = []
                    self.tileFeatureIndex[t[1]].append((t[0], action))
                    cursor.execute("SELECT tile FROM test.hierarchy WHERE child=" + str(t[1]))
                    tileId = cursor.fetchall()[0][0]
                    if tileId not in self.tileFeatureIndex:
                        self.tileFeatureIndex[tileId] = []
                    self.tileFeatureIndex[tileId].append((t[0], action))
                    cursor.execute("SELECT tile FROM test.hierarchy WHERE child=" + str(tileId))
                    tileId = cursor.fetchall()[0][0]
                    if tileId not in self.tileFeatureIndex:
                        self.tileFeatureIndex[tileId] = []
                    self.tileFeatureIndex[tileId].append((t[0], action))
                    cursor.execute("SELECT tile FROM test.hierarchy WHERE child=" + str(tileId))
                    tileId = cursor.fetchall()[0][0]
                    if tileId not in self.tileFeatureIndex:
                        self.tileFeatureIndex[tileId] = []
                    self.tileFeatureIndex[tileId].append((t[0], action))

    def resolveTile(self, tile, depth):
        if tile in self.tileIndex:
            if depth in self.tileIndex[tile]:
                return self.tileIndex[tile][depth]

        return self.default[depth] if depth in self.default else []

    def resolveFeatures(self, tile):
        if tile in self.tileFeatureIndex:
            return self.tileFeatureIndex[tile];

        return []


class Node(object):

    def __init__(self, id, depth, representation, box, isLink):
        self.id = id
        self.depth = depth
        self.representation = representation
        self.isLink = isLink
        self.children = []
        self.parent = None
        self.box = box
        self.features = []
        self.withoutTiles = []

    def __str__(self):
        return "Node " + self.id + ", " + str(self.representation)

    def remove(self, child):
        self.children.remove(child)
        child.parent = None

    def link(self, child):
        self.children.append(child)
        child.parent = self


# A tile contains a list of nodes where each node comes from the same tile but
# has a different representation
class Tile(object):

    def __init__(self, id, depth):
        self.id = id
        self.depth = depth
        self.nodes = []
        self.children = []

    def append(self, node):
        self.nodes.append(node)

    def link(self, childTile):
        self.children.append(childTile)

    def empty(self):
        return len(self.nodes) == 0


class SceneBuilder():

    @classmethod
    def build(cls, cursor, city, layer, representations, maxDepth, tile, startingDepth):
        tileTable = utils.CitiesConfig.tileTable(city)
        tileHierarchy = utils.CitiesConfig.tileHierarchy(city)
        featureTable = utils.CitiesConfig.featureTable(city, layer)
        cityDepth = len(utils.CitiesConfig.scales(city)) - 1
        startingDepth = 0 if startingDepth == None else startingDepth
        tilesetContinuation = (tile != None)
        maxDepth = None if maxDepth == cityDepth - 1 else maxDepth  # maxDepth is pointless in this case (no speed gain and negligible size reduction)
        customisationString = "representations={0}&weights={1}".format(",".join([a[0] for a in representations]), ",".join([str(a[1]) for a in representations]))

        rules = RuleEngine(None)
        rules.testTiles(cursor, city, layer)
        #rules.testFeatures(cursor, city, layer)

        depthCondition = ""
        if maxDepth != None or startingDepth != None:
            depthCondition = " WHERE"
            if maxDepth != None:
                depthCondition += " depth<={0}".format(maxDepth + 1)
                if startingDepth != None:
                    depthCondition += " AND"
            if startingDepth != None:
                depthCondition += " depth>={0}".format(startingDepth)

        # Build hierarchy
        if depthCondition == "":
            query = "SELECT tile, child FROM {0}".format(tileHierarchy)
        else:
            query = "SELECT {0}.tile, child FROM {0} JOIN {1} ON {0}.child={1}.tile".format(tileHierarchy, tileTable)
            query += depthCondition
        cursor.execute(query)
        rows = cursor.fetchall()
        tree = {}
        for (id, childId) in rows:
            if id not in tree:
                tree[id] = []
            tree[id].append(childId)

        def filterTiles(tree, tile, tileList):
            if tile in tree:
                for child in tree[tile]:
                    tileList[child] = True;
                    filterTiles(tree, child, tileList)

        if tilesetContinuation:
            tileList = {}   # TODO: should be a set
            tileList[tile] = True;
            filterTiles(tree, tile, tileList)

        # Go through every tile
        tiles = {}
        lvl0Nodes = []
        lvl0Tiles = []
        query = "SELECT tile, depth, bbox FROM {0}".format(tileTable)
        query += depthCondition
        cursor.execute(query)
        rows = cursor.fetchall()

        def generateNodes(tile, id, depth, box, isFeature):
            # Find requested representations for the tile at this specific depth
            reps = []
            for rep in rules.resolveTile(id, depth):
                a = utils.CitiesConfig.representation(city, layer, rep)
                a["name"] = rep
                reps.append(a)

            features = rules.resolveFeatures(id)

            # Check if representation exists in the database for the tile
            tableId = 'featuretable' if isFeature else 'tiletable'
            for rep in reps:
                fs = [f for f in features if any([depth >= x for x in f[1].keys()])]
                if tableId in rep:
                    table = rep[tableId]
                    if isFeature:
                        query = "WITH t AS (SELECT gid FROM {1} WHERE tile={2}) SELECT {0}.gid FROM {0} INNER JOIN t ON {0}.gid=t.gid LIMIT 1".format(table, featureTable, id)
                    else:
                        query = "SELECT tile FROM {0} WHERE tile={1}".format(table, id)
                    cursor.execute(query)
                    if cursor.rowcount != 0:
                        score = (1 + depth) #TODO: Temp
                        node = Node(id, depth, rep["name"], box, False)
                        node.features = fs;
                        tile.append(node)

            if depth == startingDepth:
                lvl0Tiles.append(id)

        for (id, depth, bbox) in rows if tile == None else [t for t in rows if t[0] in tileList]:
            box = None
            if bbox != None:
                box = utils.Box3D(bbox)

            tile = Tile(id, depth)
            tiles[id] = tile

            generateNodes(tile, id, depth, box, False)

            # Generate feature-level tile too if we're at the last tile depth
            if depth + 1 == cityDepth and (maxDepth == None or depth + 1 <= maxDepth):
                generateNodes(tile, id, depth + 1, box, True)

        # Linking nodes
        lvl0Nodes = []
        # For each tile at depth 0
        for t in lvl0Tiles:
            tile = tiles[t]
            # Build tile tree
            cls.linkTiles(tree, tiles, t)
            # Create scene graph by linking the nodes of the tiles
            lvl0Nodes += cls.createSceneGraph(tile)

        # Add single root if necessary
        if len(lvl0Nodes) == 1:
            root = lvl0Nodes[0]
        else:
            pmin = [float("inf"), float("inf"), float("inf")]
            pmax = [-float("inf"), -float("inf"), -float("inf")]
            for n in lvl0Nodes:
                corners = n.box.corners()
                pmin = [min(pmin[i], corners[0][i]) for i in range(0,3)]
                pmax = [max(pmax[i], corners[1][i]) for i in range(0,3)]
            box = 'Box3D({0},{1},{2},{3},{4},{5})'.format(*(pmin+pmax))
            box = utils.Box3D(box)

            root = Node(-1, -1, None, box, False)
            root.children = lvl0Nodes

        return cls.to3dTiles(root, city, layer, customisationString)

    @classmethod
    def linkTiles(cls, tree, allTiles, tileId):
        # Tile is a leaf: end recursion
        if tileId not in tree:
            return

        tile = allTiles[tileId]
        # Get children of tile
        for t in tree[tileId]:
            # Link child
            tile.link(allTiles[t])
            # Recursion
            cls.linkTiles(tree, allTiles, t)

    @classmethod
    def createSceneGraph(cls, tile):
        if tile.empty():
            childrenTopNodes = []
            for child in tile.children:
                childrenTopNodes += cls.createSceneGraph(child)
            return childrenTopNodes
        else:
            for i in range(0, len(tile.nodes) - 1):
                tile.nodes[i].link(tile.nodes[i + 1])

            for child in tile.children:
                for node in cls.createSceneGraph(child):
                    tile.nodes[-1].link(node)

            return [tile.nodes[0]]

    @classmethod
    def to3dTiles(cls, root, city, layer, customisationString):
        tiles = {
            "asset": {"version" : "1.0"},
            "geometricError": 100,  # TODO: should reflect startingDepth
            "root" : cls.to3dTiles_r(root, city, layer, customisationString, 10)[0]
        }
        return json.dumps(tiles)

    @classmethod
    def to3dTiles_r(cls, node, city, layer, customisationString, error):
        # TODO : handle combined nodes
        (c1, c2) = node.box.corners()
        center = [(c1[i] + c2[i]) / 2 for i in range(0,3)]
        xAxis = [c2[0] - c1[0], 0, 0]
        yAxis = [0, c2[1] - c1[1], 0]
        zAxis = [0, 0, c2[2] - c1[2]]
        box = center + xAxis + yAxis + zAxis
        tiles = []
        tile = {
            "boundingVolume": {
                "box": box
            },
            "geometricError": error, # TODO: keep or change?
            "children": [elt for n in node.children for elt in cls.to3dTiles_r(n, city, layer, customisationString, error + 1)]
        }
        tiles.append(tile)
        if node.representation != None:
            if node.isLink:
                tile["content"] = {
                    "url": "getScene?city={0}&layer={1}&tile={2}&depth={3}&{4}".format(city, layer, node.id, node.depth, customisationString)
                }
            else:
                tile["content"] = {
                    "url": "getTile?city={0}&layer={1}&tile={2}&representation={3}&depth={4}".format(city, layer, node.id, node.representation, node.depth)
                }
                if len(node.features) != 0:
                    tile["content"]["url"] += "&without="
                    tile["content"]["url"] += ",".join([str(f[0]) for f in node.features])
                    for feature in node.features:
                        if all([node.depth <= x for x in feature[1].keys()]):
                            # New feature: create new branch in scene graph
                            # TODO: should be appended to the parent's children
                            tiles.append(cls.to3dTiles_feature(feature, city, layer, customisationString, node.depth, error, box))

        else:
            tile["refine"] = "add"
        return tiles

    @classmethod
    def to3dTiles_feature(cls, feature, city, layer, customisationString, depth, error, box):
        tile = {
            "boundingVolume": {
                "box": box  # TODO: compute real feature box
            },
            "geometricError": error, # TODO: keep or change?
            "content" : {
                "url": "getFeature?city={0}&layer={1}&id={2}&representation={3}".format(city, layer, feature[0], feature[1][depth][0])
            },
            "children": []
            # TODO: "children": [cls.to3dTiles_feature(n, feature, layer, customisationString, error + 1)]
        }
        return tile
