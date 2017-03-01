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

    def __init__(self, id, depth, representation, weight, box, isLink):
        self.id = id
        self.depth = depth
        self.representation = representation
        self.weight = weight
        self.isLink = isLink
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
    def build(cls, cursor, city, layer, representations, maxDepth, tile, startingDepth):
        tileTable = utils.CitiesConfig.tileTable(city)
        tileHierarchy = utils.CitiesConfig.tileHierarchy(city)
        featureTable = utils.CitiesConfig.featureTable(city, layer)
        cityDepth = len(utils.CitiesConfig.scales(city)) - 1
        startingDepth = 0 if startingDepth == None else startingDepth
        tilesetContinuation = (tile != None)
        maxDepth = None if maxDepth == cityDepth - 1 else maxDepth  # maxDepth is pointless in this case (no speed gain and negligible size reduction)
        customisationString = "representations={0}&weights={1}".format(",".join([a[0] for a in representations]), ",".join([str(a[1]) for a in representations]))


        reps = []
        for rep in representations:
            r = utils.CitiesConfig.representation(city, layer, rep[0])
            r["name"] = rep[0]
            r["weight"] = rep[1]
            reps.append(r)

        reps = sorted(reps,  key=lambda e: e["detail"])

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
        for r in rows:
            if r[0] not in tree:
                tree[r[0]] = []
            tree[r[0]].append(r[1])

        def filterTiles(tree, tile, tileList):
            if tile in tree:
                for child in tree[tile]:
                    tileList[child] = True;
                    filterTiles(tree, child, tileList)

        if tilesetContinuation:
            tileList = {}
            tileList[tile] = True;
            filterTiles(tree, tile, tileList)

        # Go through every tile
        nodes = {}
        lvl0Nodes = []
        lvl0Tiles = []
        query = "SELECT tile, depth, bbox FROM {0}".format(tileTable)
        query += depthCondition
        cursor.execute(query)
        rows = cursor.fetchall()
        for r in rows if tile == None else [t for t in rows if t[0] in tileList]:
            depth = r[1]
            if r[2] != None:
                box = utils.Box3D(r[2])

            # Go through every representations in order of increasing detail
            existingRepresentations = []
            for rep in reps:
                if 'tiletable' in rep:
                    query = "SELECT tile FROM {0} WHERE tile={1} LIMIT 1".format(rep['tiletable'], r[0])
                    cursor.execute(query)
                    if cursor.rowcount != 0:
                        score = (1 + depth) * rep['weight'] #TODO: Temp
                        existingRepresentations.append(Node(r[0], depth, rep["name"], score, box, False if maxDepth == None else depth == maxDepth + 1))

                if depth + 1 == cityDepth and (maxDepth == None or depth + 1 <= maxDepth):
                    if 'featuretable' in rep:
                        query = "WITH t AS (SELECT gid FROM {1} WHERE tile={2}) SELECT {0}.gid FROM {0} INNER JOIN t ON {0}.gid=t.gid LIMIT 1".format(rep['featuretable'], featureTable, r[0])
                        cursor.execute(query)
                        if cursor.rowcount != 0:
                            score = (1 + depth + 1) * rep['weight'] #TODO: Temp
                            existingRepresentations.append(Node(r[0], depth + 1, rep["name"], score, box, False))

            # Linking node's representations
            nodeRep = []
            for i, node in enumerate(existingRepresentations):
                nodeRep.append(node)
                if i != 0:
                    nodeRep[i-1].children.append(node)
                    node.parent = nodeRep[i-1]
            nodes[r[0]] = nodeRep

            if depth == startingDepth:
                lvl0Tiles.append(r[0])

        # Linking nodes
        lvl0Nodes = []
        # For each tile at depth 0
        for n in lvl0Tiles:
            # Ordered list (by detail) of representations of the node n
            noderep = nodes[n]
            # Build node/representation tree
            children = cls.addChildren(tree, nodes, n)
            # Link children nodes to level 0 nodes
            if len(noderep) == 0:
                # No level 0 tiles: children become level 0 tiles
                for nr in children:
                    lvl0Nodes.append(nr[0])
            else:
                # There is at least one representation for the levl 0 tile
                # Add most detailed representation as level 0 node
                lvl0Nodes.append(noderep[0])
                #for nr in children:
                    # Add children to least detailed representation
                #    noderep[-1].add(nr[0])
        """
        for r in rows:
            if len(nodes[r[0]]) != 0:
                if len(nodes[r[1]]) != 0:
                    nodes[r[0]][-1].add(nodes[r[1]][0])
        """
        # Reorganise hierarchy based on weights
        lvl0Nodes = cls.pushUp(lvl0Nodes)

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

            root = Node(-1, -1, None, 0, box, False)
            root.children = lvl0Nodes

        return cls.to3dTiles(root, city, layer, customisationString)

    @classmethod
    def addChildren(cls, tree, allNodes, nodeId):
        # Node is a leaf: end recursion
        if nodeId not in tree:
            return []

        children = []
        # For each child node
        for n in tree[nodeId]:
            # Ordered list (by detail) of representations of the node n
            nr = allNodes[n]
            if len(nr) != 0:
                children.append(nr)

        noChild = len(children) == 0
        for n in tree[nodeId]:
            # Recursion
            c = cls.addChildren(tree, allNodes, n)
            # If children nodes have no representation, check if there are any
            # representations lower in the tree and add them as children
            if noChild:
                children += c

        # Ordered list (by detail) of representations of the current node
        nodeReps = allNodes[nodeId]
        if len(nodeReps) != 0:
            for nr in children:
                # Add children to least detailed representation
                nodeReps[-1].add(nr[0])

        return children

    @classmethod
    def pushUp(cls, lvl0Nodes):
        newLvl0Nodes = []
        for root in lvl0Nodes:
            lvl0NodeIsReplaced = False

            toRemove = []
            toCombine = {}
            # Find which node to move upwards
            for n in walk(root):
                # Find highest node with witch to combine n
                highestNode = cls.findHighestNode(n.weight, n)
                if highestNode != n:
                    # If highest node not yet registered
                    if highestNode not in toCombine:
                        toCombine[highestNode] = []
                    # Indicate that n will be combined with highestNode
                    toCombine[highestNode].append(n)
                    toRemove.append(n)

            # Remove parent link for moving nodes
            while len(toRemove) != 0:
                toRemove2 = []
                for n in toRemove:
                    parent = n.parent
                    parent.remove(n)
                    if len(parent.children) == 0 and parent not in toCombine:
                        toRemove2.append(parent)
                toRemove = toRemove2

            # Combine nodes
            for n in toCombine:
                if len(n.children) == 0:
                    # All children were moved upwards : replace node
                    if n.parent == None:
                        # No parent: these are new lvl0 nodes
                        lvl0NodeIsReplaced = True
                        for combiners in toCombine[n]:
                            newLvl0Nodes.append(combiners)
                    else:
                        for combiners in toCombine[n]:
                            n.parent.add(combiners)
                        n.parent.remove(n)
                else:
                    # Combine TODO: combinees not handled yet!
                    for combiners in toCombine[n]:
                        n.combinees.append(combiners)
            if not lvl0NodeIsReplaced:
                newLvl0Nodes.append(root)

        return newLvl0Nodes

    @classmethod
    def findHighestNode(cls, w, node):
        if node.parent == None:
            return node
        if node.parent.weight >= w:
            return cls.findHighestNode(w, node.parent)
        else:
            return node

    @classmethod
    def to3dTiles(cls, root, city, layer, customisationString):
        tiles = {
            "asset": {"version" : "1.0"},
            "geometricError": 500,  # TODO: should reflect startingDepth
            "root" : cls.to3dTiles_r(root, city, layer, customisationString)
        }
        return json.dumps(tiles)

    @classmethod
    def to3dTiles_r(cls, node, city, layer, customisationString):
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
            "geometricError": 200 / (node.weight + 2),# TODO
            "children": [cls.to3dTiles_r(n, city, layer, customisationString) for n in node.children]
        }
        if node.representation != None:
            if node.isLink:
                tile["content"] = {
                    "url": "getScene?city={0}&layer={1}&tile={2}&depth={3}&{4}".format(city, layer, node.id, node.depth, customisationString)
                }
            else:
                tile["content"] = {
                    "url": "getTile?city={0}&layer={1}&tile={2}&representation={3}&depth={4}".format(city, layer, node.id, node.representation, node.depth)
                }
        else:
            tile["refine"] = "add"
        return tile
