# Building server

This is a prototype for a simple WFS server that retrieves polyhedral surfaces
from a POSTGIS database and sends them back in a glTF file.

## Installation

### Python configuration

The server uses python 3.

Requirements:

    - cython
    - numpy
    - triangle
    - psycopg2
    - flask
    - flask-restplus
    - pyyaml

    pip install .

Development requirements:

    - nose

Production requirements:

    - uwsgi

### Run unit tests

    ./test/testsuite

## Configuration

Modify the file *conf/building.yml* to match your postgres configuration.

## Generating the quadtree and the tile association

    ./building-server-processdb.py conf/building.yml <city>

## Launch the server with uwsgi

    uwsgi --yml conf/building.uwsgi.yml

## Example

    http://localhost:9090/?query=getCities

    http://localhost:9090/?query=getGeometry&city=montreal&tile=1/4/2&format=GeoJSON
