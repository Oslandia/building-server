#!/usr/bin/env python
# -*- coding: utf-8 -*-
import struct
import binascii
import math
import triangle

def toglTF(rows,origin = [0,0,0]):
	"""
	Converts Well-Known Binary geometry to glTF file
	"""
	nodes = [];
	for i in range(0, len(rows)):
		mp = parse(bytes(rows[i][0]));
		triangles = [];
		for poly in mp:
			if(len(poly) != 1):
				print "No support for inner polygon rings"
			else:
				if(len(poly[0]) > 3):
					triangles.extend(triangulate(poly[0]));
					#print poly
					#print len(poly[0])
				else:
					triangles.append(poly[0])
		nodes.append(triangles)
	moveOrigin(nodes, origin);
	data = ([], [], [], [])
	for i in range(0,len(nodes)):
		ptsIdx = indexation(nodes[i]);
		packedVertices = ''.join(ptsIdx[0])
		data[0].append(packedVertices)
		data[1].append(struct.pack('H'*len(ptsIdx[1]), *ptsIdx[1]))
		data[2].append(len(ptsIdx[0]))
		data[3].append(len(ptsIdx[1]))
	outputJSON(data)
	outputBin(data)

	#print nodes

def outputBin(data):
	binary = ''.join(data[1])
	binary = binary + ''.join(data[0])
	return binary

def outputJSON(data):
	# Buffer
	nodeNb = len(data[0])
	sizeIdx = []
	sizeVce = []
	for i in range(0, nodeNb):
		sizeVce.append(len(data[0][i]))
		sizeIdx.append(len(data[1][i]))


	buffers = """\
"objects": {{
	"byteLength": {0},
	"type": "arraybuffer",
	"uri": 
}}""".format("k")#sum(sizeVce) + sum(sizeIdx))

	# Buffer view
	bufferViews = """\
"BV_indices": {{
	"buffer": "objects",
	"byteLength": {0},
	"byteOffset": 0,
	"target": 34963
}},
"BV_vertices": {{
	"buffer": "objects",
	"byteLength": {1},
	"byteOffset": {0},
	"target": 34962
}}""".format(sum(sizeIdx), sum(sizeVce))

	# Accessor
	accessors = ""
	for i in range(0, nodeNb):
		accessors = accessors + """\
"AI_{0}": {{
	"bufferView": "BV_indices",
    "byteOffset": {1},
    "byteStride": 4,
    "componentType": 5123,
    "count": {3},
    "type": "SCALAR"
}},
"AV_{0}": {{
	"bufferView": "BV_vertices",
    "byteOffset": {2},
    "byteStride": 12,
    "componentType": 5126,
    "count": {4},
    "type": "VEC3"
}},""".format(i, 0 if i == 0 else sizeIdx[i-1], 0 if i == 0 else sizeVce[i-1], data[3][i], data[2][i])

	# Mesh
	meshes = ""
	for i in range(0, nodeNb):
		meshes = meshes + """\
"M{0}": {{
	"attributes": {{
		"POSITION": "AV{0}"
	}}
	"indices": "AI{0}"
	"material": "defaultMaterial"
	"mode": 4
}},""".format(i)

	# Nodes
	nodes = ""
	for i in range(0, nodeNb):
		nodes = nodes + """\
"N{0}": {{
	"meshes": [
		"M{0}"
	]
}},""".format(i)
	sceneNodes = ""
	for i in range(0, nodeNb):
		sceneNodes = sceneNodes + "N{0},".format(i)

	# Final glTF
	JSON = """\
{{
	"scene": "defaultScene",
	"scenes": {{
		"defaultScene": {{
			"nodes": [
				{0}
			]
		}}
	}},
	"nodes": {{
		{1}
	}},
	"mesh": {{
		{2}
	}},
	"accessors": {{
		{3}
	}},
	"bufferViews": {{
		{4}
	}},
	"buffers": {{
		{5}
	}},
	"materials": {{
		"defaultMaterial": {{
			"name": "None"
		}}
	}}
}}""".format(sceneNodes, nodes, meshes, accessors, bufferViews, buffers)

	return JSON

def moveOrigin(nodes, delta):
	"""
	Translates all the point by minus delta
	Packs the coordinates into floats
	"""
	for n in nodes:
		for t in n:
			for i in range(0,3):
				t[i] = struct.pack('fff', t[i][0] - delta[0], t[i][1] - delta[1], t[i][2] - delta[2])


def indexation(triangles):
	"""
	Creates an index for points
	Replaces points in triangles by their index
	"""
	index = {};
	indices = [];
	maxIdx = 0;

	for t in triangles:
		for pt in t:
			if pt in index:
				indices.append(index[pt]);
			else:
				index[pt] = maxIdx;
				indices.append(maxIdx);
				maxIdx+=1;

	return (index.keys(), indices)


def triangulate(polygon):
	"""
	Triangulates 3D polygons
	"""
	vect1 = [polygon[1][0] - polygon[0][0],
             polygon[1][1] - polygon[0][1],
             polygon[1][2] - polygon[0][2]]
	vect2 = [polygon[2][0] - polygon[0][0],
             polygon[2][1] - polygon[0][1],
             polygon[2][2] - polygon[0][2]]
	vectProd = [vect1[1] * vect2[2] - vect1[2] * vect2[1],
                vect1[2] * vect2[0] - vect1[0] * vect2[2],
                vect1[0] * vect2[1] - vect1[1] * vect2[0]]
	polygon2D = [];
	segments = range(len(polygon));
	segments.append(0);
	# triangulation of the polygon projected on planes (xy) (zx) or (yz)
   	if(math.fabs(vectProd[0]) > math.fabs(vectProd[1]) and math.fabs(vectProd[0]) > math.fabs(vectProd[2])):
		# (yz) projection
		for v in range(0,len(polygon)):
			polygon2D.append([polygon[v][1], polygon[v][2]]);
	elif(math.fabs(vectProd[1]) > math.fabs(vectProd[2])):
		# (zx) projection
		for v in range(0,len(polygon)):
			polygon2D.append([polygon[v][0], polygon[v][2]]);
	else:
		# (xy) projextion
		for v in range(0,len(polygon)):
			polygon2D.append([polygon[v][0], polygon[v][1]]);

	trianglesIdx = triangle.triangulate({'vertices': polygon2D, 'segments': segments})['triangles'];
	triangles = [];

	for t in trianglesIdx:
		triangles.append([polygon[t[0]], polygon[t[1]],polygon[t[2]]])

	return triangles


def parse(wkb):
	"""
	Expects Multipolygon Z
	"""
	multiPolygon = [];
	#length = len(wkb)
	#print length
	#byteorder = struct.unpack('b', wkb[0:1])
	#print byteorder
	#geomtype = struct.unpack('I', wkb[1:5])	# 1006 (Multipolygon Z)
	#print geomtype
	geomNb = struct.unpack('I', wkb[5:9])[0];
	#print geomNb
	#print struct.unpack('b', wkb[9:10])[0];
	#print struct.unpack('I', wkb[10:14])[0];	# 1003 (Polygon)
	#print struct.unpack('I', wkb[14:18])[0];	# num lines
	#print struct.unpack('I', wkb[18:22])[0];	# num points
	offset = 9;
	for i in range(0, geomNb):
		offset += 5;#struct.unpack('bI', wkb[offset:offset+5])[0];	# 1 (byteorder), 1003 (Polygon)
		lineNb = struct.unpack('I', wkb[offset:offset+4])[0];
		offset += 4;
		polygon = [];
		for j in range(0, lineNb):
			pointNb = struct.unpack('I', wkb[offset:offset+4])[0];	# num points
			offset += 4;
			line = [];
			for k in range(0, pointNb-1):
				point = struct.unpack('ddd', wkb[offset:offset+24]);
				offset += 24;
				line.append(point);
			offset += 24;	# skip redundant point
			polygon.append(line);
		multiPolygon.append(polygon);
	#print multiPolygon;
	#print len(multiPolygon);
	return multiPolygon;



# test code

import psycopg2
connection = psycopg2.connect('dbname=lyon user=jeremy')
cursor = connection.cursor()

cursor.execute("select ST_AsBinary(geom) from lyon1 AS g limit 3")
rows = cursor.fetchall();
#wkb_bin = cursor.fetchone()[0]
toglTF(rows, [1842315.409503, 5176011.019509, 201.437597]);