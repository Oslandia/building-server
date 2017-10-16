#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
import time
import sys
import yaml
from io import StringIO

from .database import Session
from .utils import CitiesConfig, Box3D


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
            scores = Session.score_for_polygon(city, poly, scoref)
            qt += time.time() - qt0

            geoms = []
            for score in scores:
                box3D = Box3D(score['box3d'])
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

    quadtree_data = StringIO('\n'.join([
        # row is (gid, quadtile, weight)
        '\t'.join((str(j[0]), str(i), str(j[2])))
        for i in index
        for j in index[i]
    ]))

    quadtree_table = '{}_quadtree'.format(CitiesConfig.table(city))
    print(quadtree_table)
    Session.db.cursor().execute("""
        drop table if exists {};
        create unlogged table {} (
            gid bigint primary key
            , quadtile varchar
            , weight real
        )
        """.format(quadtree_table, quadtree_table))

    cur = Session.db.cursor()
    cur.copy_from(quadtree_data, quadtree_table, columns=('gid', 'quadtile', 'weight'))

    # fill a new table with city values joined with the quadtree table
    # swap tables at the end
    Session.db.cursor().execute("""
        create table {city}_new as
            select c.*, q.quadtile, q.weight
            from {city} c
            join {quadtable} q using (gid);

        drop table {city};
        drop table {quadtable};
        alter table {city}_new rename to {city};
    """.format(city=CitiesConfig.table(city), quadtable=quadtree_table))

    # recreate spatial indexes and gid index
    Session.db.cursor().execute("create index on {}(gid)".format(CitiesConfig.table(city)))
    Session.db.cursor().execute("create index on {} using gist(geom)".format(CitiesConfig.table(city)))

    print("Table update time : {0}".format(time.time() - t1))
    t2 = time.time()
    Session.create_index(city, "quadtile")
    print("Index creation time : {0}".format(time.time() - t2))

    # create bbox table
    t3 = time.time()
    Session.create_bbox_table(city)

    for i in bboxIndex:
        b = bboxIndex[i]
        bbox_str = str(b[0][0]) + " " + str(b[0][1]) + " " + str(b[0][2]) \
            + "," + str(b[1][0]) + " " + str(b[1][1]) + " " + str(b[1][2])
        Session.insert_into_bbox_table(city, i, bbox_str)

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


def preprocess(args):
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
    CitiesConfig.init(str(args.cfg))

    # reinitialize the database
    Session.drop_column(args.city, "quadtile")
    Session.drop_column(args.city, "weight")
    Session.drop_bbox_table(args.city)

    # fill the database
    initDB(args.city, cityconf, args.score)
