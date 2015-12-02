#!/usr/bin/env python
# -*- coding: utf-8 -*-

import psycopg2
import urlparse
import struct

import settings
import transcode

def application(environ, start_response):
	status = "200 OK"
	response_header = [("Content-type", "application/json")] # may need to change later
	start_response(status, response_header)

	cursor, connection = connect_db()

	param = dict(urlparse.parse_qsl(environ['QUERY_STRING']))

	query = param['query']

	output = ""

	# The getGeometry query returns the geometries contained in a tile and the bounding boxes of the children tiles
	if query == 'getGeometry':
		city = param['city']
		tile = param['tile']
		outputFormat = param['format']
		offset = compute_offset(tile, city)
		cityTable = settings.CITIES[city]['tablename']

		if outputFormat == "GeoJSON":
			cursor.execute("select gid, ST_AsGeoJSON(ST_Transform(\"geom\"::geometry,3946),0, 1) AS \"geom\" from {0} where quadtile='{1}'".format(cityTable, tile))
			rows = cursor.fetchall();
			output = '{"type": "FeatureCollection", "crs":{"type":"name","properties":{"name":"EPSG:3946"}}, "features": ['
			for r in rows:
				output += '{{"type":"Feature", "id": "lyongeom.{0}", "properties":{{"gid": "{0}"}}, "geometry": {1}}}'.format(r[0], r[1])
				output += ",\n"
			if(len(rows) != 0): output = output[0:len(output)-2]
			output += ']}'
		else:
			# geometries
			cursor.execute("select ST_AsBinary(geom), Box3D(geom) from {0} where quadtile='{1}'".format(cityTable, tile))
			rows = cursor.fetchall()
			if len(rows) == 0:
				output = struct.pack('4sIIII', "glTF", 1, 20, 0, 0) # empty bglTF
				output += '{"tiles":[]}'
			else:
				bglTF = transcode.toglTF(rows, True, offset)
				output = bglTF

				# children bboxes
				[z,y,x] = tile.split("/")
				z = int(z); y = int(y); x = int(x);
				condition = "quadtile='{0}' or quadtile='{1}' or quadtile='{2}' or quadtile='{3}'".format(
					str(z+1) + "/" + str(2*y) + "/" + str(2*x),
					str(z+1) + "/" + str(2*y+1) + "/" + str(2*x),
					str(z+1) + "/" + str(2*y) + "/" + str(2*x+1),
					str(z+1) + "/" + str(2*y+1) + "/" + str(2*x+1))
				cursor.execute("select quadtile, bbox from {0}_bbox where {1}".format(cityTable,condition))
				rows = cursor.fetchall()
				output += '{"tiles":['
				for r in rows:
					output += '{"id":"' + r[0] + '","bbox":' + formatBbox2D(r[1]) + '},'
				if len(rows) != 0:
					output = output[0:len(output)-1]
				output += "]}"

		cursor.close()
		connection.close()

	# The getCities query returns a list of all available cities and their metadata
	elif query == 'getCities':
		output = str(settings.CITIES).replace('\'', '"');

	# The getCity query returns the level-0 tiles bounding boxes
	elif query == 'getCity':
		city = param['city']
		cityTable = settings.CITIES[city]['tablename']
		cursor.execute("select quadtile, bbox from {0}_bbox where substr(quadtile,1,1)='0'".format(cityTable))
		rows = cursor.fetchall();
		output = '{"tiles":['
		for r in rows:
			output += '{"id":"' + r[0] + '","bbox":' + formatBbox2D(r[1]) + '},'
		if len(rows) != 0:
			output = output[0:len(output)-1]
		output += "]}"
		#output = "["
		#for r in rows:
	#		output += formatBbox2D(r[0]) + ","
	#	if len(rows) != 0:
	#		output = output[0:len(output)-1]
	#	output += "]"

	return output

def formatBbox2D(string):
	return "[" + string[4:len(string)-1].replace(" ", ",") + "]"

def connect_db():
	conn_string = "host='%s' dbname='%s' user='%s' password='%s' port='%s'" % (settings.DB_INFOS['host'], settings.DB_INFOS['dbname'], settings.DB_INFOS['user'], settings.DB_INFOS['password'], settings.DB_INFOS['port'])
	conn = psycopg2.connect(conn_string)
	cursor = conn.cursor()
	return cursor, conn

def compute_offset(tile, city):
	[z,y,x] = map(int, tile.split('/'))	# tile coordinates
	[minX, minY] = settings.CITIES[city]['extent'][0]
	tileSize = settings.CITIES[city]['maxtilesize'] / (2 ** z)
	return [minX + x * tileSize, minY + y * tileSize, 0]