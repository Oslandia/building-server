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


def initDB(city, conf, scoref):
    extent = conf["extent"]
    table = conf["tablename"]
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

    # create quadtree
    for i in range(0, int(math.ceil(extentX / maxTileSize))):
        for j in range(0, int(math.ceil(extentY / maxTileSize))):
            tileExtent = tile_extent(extent, maxTileSize, i, j)

            p0 = "{0} {1}".format(tileExtent[0][0], tileExtent[0][1])
            p1 = "{0} {1}".format(tileExtent[0][0], tileExtent[1][1])
            p2 = "{0} {1}".format(tileExtent[1][0], tileExtent[1][1])
            p3 = "{0} {1}".format(tileExtent[1][0], tileExtent[0][1])
            poly = [p0, p1, p2, p3]

            qt0 = time.time()
            scores = Session.score_for_polygon(table, poly, scoref)
            qt += time.time() - qt0

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

            coord = "{0}/{1}/{2}".format(0, j, i)
            if len(geoms) > featuresPerTile:
                index[coord] = geoms[0:featuresPerTile]
                bbox = divide(tileExtent,
                              geoms[featuresPerTile:len(geoms)], 1, i * 2,
                              j * 2, maxTileSize / 2., featuresPerTile, index,
                              bboxIndex)
            else:
                bbox = superbbox()
                index[coord] = geoms

            for geom in index[coord]:
                p1 = geom[3]
                p2 = geom[4]
                bbox[0][0] = min(bbox[0][0], p1[0], p2[0])
                bbox[0][1] = min(bbox[0][1], p1[1], p2[1])
                bbox[0][2] = min(bbox[0][2], p1[2], p2[2])
                bbox[1][0] = max(bbox[1][0], p1[0], p2[0])
                bbox[1][1] = max(bbox[1][1], p1[1], p2[1])
                bbox[1][2] = max(bbox[1][2], p1[2], p2[2])
            bboxIndex[coord] = bbox

    print("Query time : {0}".format(qt))
    print("Quadtree creation total time : {0}".format(time.time() - t0))

    t1 = time.time()
    # create index
    Session.add_column(table, "quadtile", "varchar(10)")
    Session.add_column(table, "weight", "real")

    for i in index:
        for j in index[i]:
            Session.update_table(table, i, j[2], j[0])

    print("Table update time : {0}".format(time.time() - t1))
    t2 = time.time()
    Session.create_index(table, "quadtile")
    print("Index creation time : {0}".format(time.time() - t2))

    # create bbox table
    t3 = time.time()
    Session.create_bbox_table(table)

    for i in bboxIndex:
        b = bboxIndex[i]
        bbox_str = str(b[0][0]) + " " + str(b[0][1]) + " " + str(b[0][2]) \
            + "," + str(b[1][0]) + " " + str(b[1][1]) + " " + str(b[1][2])
        Session.insert_into_bbox_table(table, i, bbox_str)

    print("Bounding box table creation time : {0}".format(time.time() - t3))


def divide(extent, geometries, depth, xOffset, yOffset, tileSize,
           featuresPerTile, index, bboxIndex):
    superBbox = superbbox()

    for i in range(0, 2):
        for j in range(0, 2):
            tileExtent = tile_extent(extent, tileSize, i, j)

            geoms = []
            for g in geometries:
                if inside(tileExtent, g[1]):
                    geoms.append(g)
            if len(geoms) == 0:
                continue

            coord = "{0}/{1}/{2}".format(depth, yOffset + j, xOffset + i)
            if len(geoms) > featuresPerTile:
                index[coord] = geoms[0:featuresPerTile]
                bbox = divide(tileExtent, geoms[featuresPerTile:len(geoms)],
                              depth + 1, (xOffset + i) * 2, (yOffset + j) * 2,
                              tileSize / 2., featuresPerTile, index, bboxIndex)
            else:
                bbox = superbbox()
                index[coord] = geoms

            for geom in index[coord]:
                p1 = geom[3]
                p2 = geom[4]
                bbox[0][0] = min(bbox[0][0], p1[0], p2[0])
                bbox[0][1] = min(bbox[0][1], p1[1], p2[1])
                bbox[0][2] = min(bbox[0][2], p1[2], p2[2])
                bbox[1][0] = max(bbox[1][0], p1[0], p2[0])
                bbox[1][1] = max(bbox[1][1], p1[1], p2[1])
                bbox[1][2] = max(bbox[1][2], p1[2], p2[2])
            bboxIndex[coord] = bbox

            superBbox[0][0] = min(superBbox[0][0], bbox[0][0])
            superBbox[0][1] = min(superBbox[0][1], bbox[0][1])
            superBbox[0][2] = min(superBbox[0][2], bbox[0][2])
            superBbox[1][0] = max(superBbox[1][0], bbox[1][0])
            superBbox[1][1] = max(superBbox[1][1], bbox[1][1])
            superBbox[1][2] = max(superBbox[1][2], bbox[1][2])
    return superBbox

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
    if (("tablename" not in cityconf) or ("extent" not in cityconf)
            or ("maxtilesize" not in cityconf)):
        print(("ERROR: '{0}' city is not properly defined in '{1}'"
              .format(args.city, args.cfg)))
        sys.exit()

    # open database
    app = type('', (), {})()
    app.config = ymlconf_db
    Session.init_app(app)
    utils.CitiesConfig.init(str(args.cfg))

    # reinitialize the database
    tablename = cityconf['tablename']
    Session.drop_column(tablename, "quadtile")
    Session.drop_column(tablename, "weight")
    Session.drop_bbox_table(tablename)

    # fill the database
    initDB(args.city, cityconf, args.score)
