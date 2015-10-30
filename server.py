#!/usr/bin/env python
# -*- coding: utf-8 -*-

import psycopg2
import urlparse

import settings
import transcode

def application(environ, start_response):
	status = "200 OK"
	response_header = [("Content-type", "application/json")] # may need to change later
	start_response(status, response_header)

	cursor, connection = connect_db()

	param = dict(urlparse.parse_qsl(environ['QUERY_STRING']))

	tile = param['tile']
	city = param['city']
	outputFormat = param['format']
	offset = compute_offset(tile, city)
	cityTable = settings.CITIES[city]['tablename']

	if outputFormat == "GeoJSON":
		cursor.execute("select ST_AsGeoJSON(geom) from {0} where quadtile='{1}'".format(cityTable, tile))
		rows = cursor.fetchall();
		output = ""
		for r in rows:
			output += r[0] + ",\n"
		output = output[0:len(output)-2]
	else:	
		cursor.execute("select ST_AsBinary(geom) from {0} where quadtile='{1}'".format(cityTable, tile))
		rows = cursor.fetchall();
		output = transcode.toglTF(rows, offset);

	return output

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