#!/usr/bin/env python
# -*- coding: utf-8 -*-

import psycopg2
import math
import pprint
import time
import sys
import settings

THRESHOLD = 50

def inside(box, point):
	return box[0][0] <= point[0] < box[1][0] and box[0][1] <= point[1] < box[1][1]

def processDB(connection, extent, table, cursor, maxTileSize = 2000):
	extentX = extent[1][0] - extent[0][0]
	extentY = extent[1][1] - extent[0][1]
	print extentX
	print extentY

	index = {}
	bboxIndex = {}
	t0 = time.time()
	qt = 0

	# create quadtree
	for i in range(0, int(math.ceil(extentX / maxTileSize))):
		for j in range(0, int(math.ceil(extentY / maxTileSize))):
			tileExtent = [[extent[0][0] + i*maxTileSize, extent[0][1] + j*maxTileSize], [extent[0][0] + (i+1)*maxTileSize, extent[0][1] + (j+1)*maxTileSize]]
			p1 = "{0} {1}".format(tileExtent[0][0], tileExtent[0][1])
			p2 = "{0} {1}".format(tileExtent[0][0], tileExtent[1][1])
			p3 = "{0} {1}".format(tileExtent[1][0], tileExtent[1][1])
			p4 = "{0} {1}".format(tileExtent[1][0], tileExtent[0][1])
			scoreFunction = "ST_Area(Box2D(geom))"#"ST_NPoints(geom)" # "ST_3DArea(geom)" #FIX : clean polyhedral surfaces before calling the function
			query = "SELECT gid, Box2D(geom), {4} AS \"score\" FROM {5} WHERE (geom && 'POLYGON(({0}, {1}, {2}, {3}, {0}))'::geometry) ORDER BY score DESC".format(p1, p2, p3, p4, scoreFunction, table)
			qt0 = time.time()
			cursor.execute(query)
			qt += time.time() - qt0
			rows = cursor.fetchall()
			geoms = []
			for r in rows:
				box2D = r[1][4:len(r[1])-1]	# remove "BOX(" and ")"
				part = box2D.partition(',')
				p1 = part[0].partition(' ')
				p2 = part[2].partition(' ')
				p1 = [float(p1[0]), float(p1[2])]
				p2 = [float(p2[0]), float(p2[2])]
				centroid = ((p2[0] + p1[0]) / 2., (p2[1] + p1[1]) / 2.)
				if inside(tileExtent, centroid):
					geoms.append((r[0], centroid, r[2], p1, p2))
			if len(geoms) == 0:
				continue

			coord = "{0}/{1}/{2}".format(0, j, i)
			if len(geoms) > THRESHOLD:
				index[coord] = geoms[0:THRESHOLD]
				bbox = divide(tileExtent, geoms[THRESHOLD:len(geoms)], 1, i * 2, j * 2, maxTileSize / 2., index, bboxIndex)
			else:
				bbox = [[float("inf"),float("inf")],[-float("inf"),-float("inf")]]
				index[coord] = geoms

			for geom in index[coord]:
				p1 = geom[3]
				p2 = geom[4]
				bbox[0][0] = min(bbox[0][0], p1[0], p2[0])
				bbox[0][1] = min(bbox[0][1], p1[1], p2[1])
				bbox[1][0] = max(bbox[1][0], p1[0], p2[0])
				bbox[1][1] = max(bbox[1][1], p1[1], p2[1])
			bboxIndex[coord] = bbox


	"""pp = pprint.PrettyPrinter(indent = 4, width = 80, depth = 3)
	pp.pprint(index)
	pp.pprint(bboxIndex)
	idSet = set()
	for i in index:
		for j in index[i]:
			if j[0] not in idSet:
				idSet.add(j[0])
			else:
				print "{0} sadface".format(j[0])
	print len(idSet)"""
	print "Query time : {0}".format(qt)
	print "Quadtree creation total time : {0}".format(time.time() - t0)

	t1 = time.time()
	# create index
	cursor.execute("ALTER TABLE {0} ADD COLUMN quadtile varchar(10)".format(table))
	for i in index:
		for j in index[i]:
			query = "UPDATE {2} SET quadtile = '{0}' WHERE gid = {1}".format(i, j[0], table)
			cursor.execute(query)
	print "Table update time : {0}".format(time.time() - t1)
	t2 = time.time()
	cursor.execute("CREATE INDEX tileIdx_{0} ON {0} (quadtile)".format(table))
	print "Index creation time : {0}".format(time.time() - t2)

	# create bbox table
	t3 = time.time()
	cursor.execute("CREATE TABLE {0} (quadtile varchar(10) PRIMARY KEY, bbox Box2D)".format(table + "_bbox"))
	for i in bboxIndex:
		b = bboxIndex[i]
		bbox_str = str(b[0][0]) + " " + str(b[0][1]) + "," + str(b[1][0]) + " " + str(b[1][1])
		query = "INSERT INTO {0} values ('{1}', Box2D(ST_GeomFromText('LINESTRING({2})')))".format(table + "_bbox", i, bbox_str) # a simpler query probabliy exists
		cursor.execute(query)
	print "Bounding box table creation time : {0}".format(time.time() - t3)
	connection.commit()
	
	# Query timing
	"""
	tileExtent = [[1843816.94334, 5176036.4587], [1845816.94334, 5178036.4587]]
	p1 = "{0} {1}".format(tileExtent[0][0], tileExtent[0][1])
	p2 = "{0} {1}".format(tileExtent[0][0], tileExtent[1][1])
	p3 = "{0} {1}".format(tileExtent[1][0], tileExtent[1][1])
	p4 = "{0} {1}".format(tileExtent[1][0], tileExtent[0][1])
	query = "SELECT gid FROM lyongeom WHERE (geom && 'POLYGON(({0}, {1}, {2}, {3}, {0}))'::geometry)".format(p1, p2, p3, p4)
	t3 = time.time()
	cursor.execute(query)
	print time.time() - t3
	print cursor.rowcount
	t3 = time.time()
	cursor.execute("SELECT gid FROM lyongeom WHERE quadtile = '0/3/3'")
	print time.time() - t3
	print cursor.rowcount"""


def divide(extent, geometries, depth, xOffset, yOffset, tileSize, index, bboxIndex):
	superBbox = [[float("inf"),float("inf")],[-float("inf"),-float("inf")]]
	for i in range(0, 2):
		for j in range(0, 2):
			tileExtent = [[extent[0][0] + i*tileSize, extent[0][1] + j*tileSize], [extent[0][0] + (i+1)*tileSize, extent[0][1] + (j+1)*tileSize]]
			geoms = []
			for g in geometries:
				if inside(tileExtent, g[1]):
					geoms.append(g)
			if len(geoms) == 0:
				continue

			coord = "{0}/{1}/{2}".format(depth, yOffset + j, xOffset + i)
			if len(geoms) > THRESHOLD:
				index[coord] = geoms[0:THRESHOLD]
				bbox = divide(tileExtent, geoms[THRESHOLD:len(geoms)], depth + 1, (xOffset + i) * 2, (yOffset + j) * 2, tileSize / 2., index, bboxIndex)
			else:
				bbox = [[float("inf"),float("inf")],[-float("inf"),-float("inf")]]
				index[coord] = geoms

			for geom in index[coord]:
				p1 = geom[3]
				p2 = geom[4]
				bbox[0][0] = min(bbox[0][0], p1[0], p2[0])
				bbox[0][1] = min(bbox[0][1], p1[1], p2[1])
				bbox[1][0] = max(bbox[1][0], p1[0], p2[0])
				bbox[1][1] = max(bbox[1][1], p1[1], p2[1])
			bboxIndex[coord] = bbox

			superBbox[0][0] = min(superBbox[0][0], bbox[0][0])
			superBbox[0][1] = min(superBbox[0][1], bbox[0][1])
			superBbox[1][0] = max(superBbox[1][0], bbox[1][0])
			superBbox[1][1] = max(superBbox[1][1], bbox[1][1])
	return superBbox


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
	cursor.execute("ALTER TABLE " + city["tablename"] + " DROP COLUMN IF EXISTS quadtile")	#reset table
	cursor.execute("DROP TABLE IF EXISTS " + city["tablename"] + "_bbox")	#reset table
	connection.commit()

	processDB(connection, city["extent"], city["tablename"], cursor, city["maxtilesize"])
	cursor.close()
	connection.close()
