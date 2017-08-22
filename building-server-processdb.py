#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
import time
import sys
import argparse
import yaml

from building_server.database import Session
from building_server import utils


def inside(box, point):
    return ((box[0][0] <= point[0] < box[1][0])
            and (box[0][1] <= point[1] < box[1][1]))


def tile_extent(extent, size, i, j):
    minExtent = [extent[0][0] + i*size,
                 extent[0][1] + j*size]
    maxExtent = [extent[0][0] + (i+1)*size,
                 extent[0][1] + (j+1)*size]
    return [minExtent, maxExtent]


def superbbox():
    return [[float("inf"), float("inf"), float("inf")],
            [-float("inf"), -float("inf"), -float("inf")]]

def addPointsToBox(bbox, p1, p2):
    bbox[0][0] = min(bbox[0][0], p1[0], p2[0])
    bbox[0][1] = min(bbox[0][1], p1[1], p2[1])
    bbox[0][2] = min(bbox[0][2], p1[2], p2[2])
    bbox[1][0] = max(bbox[1][0], p1[0], p2[0])
    bbox[1][1] = max(bbox[1][1], p1[1], p2[1])
    bbox[1][2] = max(bbox[1][2], p1[2], p2[2])

def addBoxToBox(superBbox, bbox):
    superBbox[0][0] = min(superBbox[0][0], bbox[0][0])
    superBbox[0][1] = min(superBbox[0][1], bbox[0][1])
    superBbox[0][2] = min(superBbox[0][2], bbox[0][2])
    superBbox[1][0] = max(superBbox[1][0], bbox[1][0])
    superBbox[1][1] = max(superBbox[1][1], bbox[1][1])
    superBbox[1][2] = max(superBbox[1][2], bbox[1][2])

def counter(init):
    count = init - 1
    def f():
        nonlocal count
        count += 1
        return count
    return f

def initDB(city, conf, scoref):
    extent = conf["extent"]
    maxTileSize = conf["maxtilesize"]
    featuresPerTile = conf["featurespertile"]

    extentX = extent[1][0] - extent[0][0]
    extentY = extent[1][1] - extent[0][1]
    print(extentX)
    print(extentY)

    index = {}
    bboxIndex = {}
    t0 = time.time()
    qt = 0
    nextId = counter(1)   # id 0 = root

    # create quadtree
    lvl0Tiles = []
    superBbox = superbbox()
    for i in range(0, int(math.ceil(extentX / maxTileSize))):
        for j in range(0, int(math.ceil(extentY / maxTileSize))):
            tileExtent = tile_extent(extent, maxTileSize, i, j)

            p0 = "{0} {1}".format(tileExtent[0][0], tileExtent[0][1])
            p1 = "{0} {1}".format(tileExtent[0][0], tileExtent[1][1])
            p2 = "{0} {1}".format(tileExtent[1][0], tileExtent[1][1])
            p3 = "{0} {1}".format(tileExtent[1][0], tileExtent[0][1])
            poly = [p0, p1, p2, p3]

            qt0 = time.time()
            # Gets all polygons' id, box3d and score
            scores = Session.score_for_polygon(city, poly, scoref)
            qt += time.time() - qt0

            # Adds geometries with their centroid inside the current tile to the tile
            geoms = []
            for score in scores:
                box3D = utils.Box3D(score['box3d'])
                centroid = box3D.centroid()

                if inside(tileExtent, centroid):
                    corners = box3D.corners()
                    geoms.append((score['gid'], centroid, score['score'],
                                 corners[0], corners[1]))

            if len(geoms) == 0:
                continue

            # if there is too much features in the current tile, it is subdivided
            # in subtiles. The tiles with the highest scores go into the parent tile
            # and the ones with the lowest scores go into the children tiles.
            # There is no mention of score into the subdivision process because
            # we use the fact that they are already sorted in descending order
            # (done in score_for_polygon function of database.py)
            tileId = nextId() # generation of a unique id
            if len(geoms) > featuresPerTile:
                index[tileId] = geoms[0:featuresPerTile]
                (bbox, c) = divide(tileExtent, geoms[featuresPerTile:len(geoms)],
                                   tileId, maxTileSize / 2, featuresPerTile, index,
                                   bboxIndex, nextId)
                lvl0Tiles.append(c)
            else:
                bbox = superbbox()
                index[tileId] = geoms

            for (_, _, _, p1, p2) in index[tileId]:
                addPointsToBox(bbox, p1, p2)
            addBoxToBox(superBbox, bbox)

            bboxIndex[tileId] = bbox
    index[0] = []
    bboxIndex[0] = superBbox
    tree = (0,  lvl0Tiles)

    print("Query time : {0}".format(qt))
    print("Quadtree creation total time : {0}".format(time.time() - t0))

    t1 = time.time()
    Session.create_hierarchy_tables(city)

    for tileIndex in index:
        b = bboxIndex[tileIndex]
        bbox_str = str(b[0][0]) + " " + str(b[0][1]) + " " + str(b[0][2]) \
            + "," + str(b[1][0]) + " " + str(b[1][1]) + " " + str(b[1][2])
        Session.insert_tile(city, tileIndex, bbox_str)
        for feature in index[tileIndex]:
            Session.insert_feature(city, feature[0], tileIndex)

    Session.insert_hierarchy(city, tree)

    print("Table update time : {0}".format(time.time() - t1))


def divide(extent, geometries, tileId, tileSize,
           featuresPerTile, index, bboxIndex, nextId):
    superBbox = superbbox()
    children = []

    for i in range(0, 2):
        for j in range(0, 2):
            tileExtent = tile_extent(extent, tileSize, i, j)

            geoms = []
            for g in geometries:
                if inside(tileExtent, g[1]):
                    geoms.append(g)
            if len(geoms) == 0:
                continue

            childTileId = nextId()
            if len(geoms) > featuresPerTile:
                index[childTileId] = geoms[0:featuresPerTile]
                (bbox, c) = divide(tileExtent,
                                   geoms[featuresPerTile:len(geoms)], childTileId,
                                   tileSize / 2, featuresPerTile, index,
                                   bboxIndex, nextId)
                children.append(c)
            else:
                children.append((childTileId, []))
                bbox = superbbox()
                index[childTileId] = geoms

            for (_, _, _, p1, p2) in index[childTileId]:
                addPointsToBox(bbox, p1, p2)
            bboxIndex[childTileId] = bbox
            addBoxToBox(superBbox, bbox)

    return (superBbox, (tileId, children))

if __name__ == '__main__':

    # arg parse
    descr = 'Process a database to build an octree for building-server'
    parser = argparse.ArgumentParser(description=descr)

    cfg_help = 'configuration file'
    parser.add_argument('cfg', metavar='cfg', type=str, help=cfg_help)

    city_help = 'city to process'
    parser.add_argument('city', metavar='city', type=str, help=city_help)

    score_help = 'score function with "ST_Area(Box2D(geom))" as default value'
    parser.add_argument('--score', metavar='score', type=str, help=score_help,
                        default="ST_Area(Box2D(geom))")

    args = parser.parse_args()

    # load configuration
    ymlconf_cities = None
    with open(args.cfg, 'r') as f:
        try:
            ymlconf_cities = yaml.load(f)['cities']
        except:
            print("ERROR: ", sys.exc_info()[0])
            f.close()
            sys.exit()

    ymlconf_db = None
    with open(args.cfg, 'r') as f:
        try:
            ymlconf_db = yaml.load(f)['flask']
        except:
            print("ERROR: ", sys.exc_info()[0])
            f.close()
            sys.exit()

    # check if the city is within the configuration
    if args.city not in ymlconf_cities:
        print(("ERROR: '{0}' city not defined in configuration file '{1}'"
               .format(args.city, args.cfg)))
        sys.exit()

    # get city configuration
    cityconf = ymlconf_cities[args.city]

    # check if the configuration is well defined for the city
    if (("tiletable" not in cityconf) or ("geometrytable" not in cityconf)
        or ("hierarchytable" not in cityconf) or ("featuretable" not in cityconf)
        or ("extent" not in cityconf) or ("maxtilesize" not in cityconf)):
        print(("ERROR: '{0}' city is not properly defined in '{1}'"
              .format(args.city, args.cfg)))
        sys.exit()

    # open database
    app = type('', (), {})()
    app.config = ymlconf_db
    Session.init_app(app)
    utils.CitiesConfig.init(str(args.cfg))

    # reinitialize the database
    Session.drop_hierarchy_tables(args.city)

    # fill the database
    initDB(args.city, cityconf, args.score)
