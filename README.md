# Building server

This is a prototype for a simple web server that retrieves polyhedral surfaces
from a POSTGIS database and sends them back in a glTF or GeoJSON file.

It relies on a Bounding Volume Hierarchy (BVH) to transmit progressively the
geometric data. A script for building the BVH is provided in this repository.

## Installation

### From sources

To use building-server from sources:

```
$ apt-get install python3-dev
$ git clone https://github.com/Oslandia/building-server
$ cd building-server
$ virtualenv -p /usr/bin/python3 venv
$ . venv/bin/activate
(venv)$ pip install --upgrade setuptools
(venv)$ pip install -e .
```

If you want to run unit tests:

```
(venv)$ pip install nose
(venv)$ nosetests
...
```

## Generating the BVH and the tile association

    ./building-server-processdb.py conf/building.yml <city>

## How to run

building-server has been tested with uWSGI and Nginx.

Once files *building.uwsgi.yml* and *building.yml* are well configurated for your
environment, you can run the building-server:

```
(venv)$ pip install uwsgi
(venv)$ uwsgi --yml conf/building.uwsgi.yml
spawned uWSGI worker 1 (pid: 5984, cores: 1)

```

In case of the next error:

```
(venv)$ uwsgi --yml conf/building.uwsgi.yml
ImportError: No module named site
(venv)$ deactivate
$ . venv/bin/activate
(venv)$ uwsgi --yml conf/building.uwsgi.yml
spawned uWSGI worker 1 (pid: 5984, cores: 1)

```

## Example

    http://localhost:9090/?query=getCities

    http://localhost:9090/?query=getGeometry&city=montreal&tile=1/4/2&format=GeoJSON
