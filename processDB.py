#!/usr/bin/env python
# -*- coding: utf-8 -*-

import psycopg2
import math
import pprint
import time
import sys
import settings

THRESHOLD = 20

def inside(box, point):
	return box[0][0] <= point[0] < box[1][0] and box[0][1] <= point[1] < box[1][1]

def processDB(connection, extent, table, cursor, maxTileSize = 2000):
	extentX = extent[1][0] - extent[0][0]
	extentY = extent[1][1] - extent[0][1]
	print extentX
	print extentY

	index = {}
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
			scoreFunction = "ST_NPoints(geom)" # "ST_3DArea(geom)" #FIX : clean polyhedral surfaces before calling the function
			query = "SELECT gid, Box2D(geom), {4} AS \"score\" FROM lyongeom WHERE (geom && 'POLYGON(({0}, {1}, {2}, {3}, {0}))'::geometry) ORDER BY score ASC".format(p1, p2, p3, p4, scoreFunction)
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
				centroid = ((float(p2[0]) + float(p1[0])) / 2., (float(p2[2]) + float(p1[2])) / 2.)
				if inside(tileExtent, centroid):
					geoms.append((r[0], centroid, r[2]))
			coord = "{0}/{1}/{2}".format(0, j, i)
			if len(geoms) > THRESHOLD:
				index[coord] = geoms[0:THRESHOLD]
				divide(tileExtent, geoms[THRESHOLD:len(geoms)], 1, i * 2, j * 2, maxTileSize / 2., index)
			else:
				index[coord] = geoms

	"""pp = pprint.PrettyPrinter(indent = 4, width = 80, depth = 1)
	pp.pprint(index)
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
	cursor.execute("ALTER TABLE lyongeom ADD COLUMN quadtile varchar(10)")
	for i in index:
		for j in index[i]:
			query = "UPDATE lyongeom SET quadtile = '{0}' WHERE gid = {1}".format(i, j[0])
			cursor.execute(query)
	print "Table update time : {0}".format(time.time() - t1)
	t2 = time.time()
	cursor.execute("CREATE INDEX tileIdx ON lyongeom (quadtile)")
	print "Index creation time : {0}".format(time.time() - t2)
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


def divide(extent, geometries, depth, xOffset, yOffset, tileSize, index):
	for i in range(0, 2):
		for j in range(0, 2):
			tileExtent = [[extent[0][0] + i*tileSize, extent[0][1] + j*tileSize], [extent[0][0] + (i+1)*tileSize, extent[0][1] + (j+1)*tileSize]]
			geoms = []
			for g in geometries:
				if inside(tileExtent, g[1]):
					geoms.append(g)
			coord = "{0}/{1}/{2}".format(depth, yOffset + j, xOffset + i)
			index[coord] = geoms
			if len(geoms) > THRESHOLD:
				index[coord] = geoms[0:THRESHOLD]
				divide(tileExtent, geoms[THRESHOLD:len(geoms)], depth + 1, (xOffset + i) * 2, (yOffset + j) * 2, tileSize / 2., index)
			else:
				index[coord] = geoms


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
	connection.commit()

	processDB(connection, city["extent"], city["tablename"], cursor, city["maxtilesize"])
	cursor.close()
	connection.close()
