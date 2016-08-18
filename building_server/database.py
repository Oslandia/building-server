# -*- coding: utf-8 -*-

from itertools import chain
from psycopg2 import connect
from psycopg2.extras import NamedTupleCursor


class Session():
    """
    Session object used as a global connection object to the db

    # FIXME: handle disconnection
    """
    db = None

    @classmethod
    def offset(cls, city, tile):
        """Returns a 3D offset for a specific tile

        Parameters
        ----------
        city : str
        tile : str
            '6/22/28'

        Returns
        -------
        offset : list
            [x, y, z] as float or None if no tile is found
        """

        sql = ("SELECT bbox from {0}_bbox WHERE quadtile = '{1}'"
               .format(city, tile))
        res = cls.query_aslist(sql)

        offset = None
        if res:
            o = res[0]
            box3D = o[6:len(o)-1]   # remove "BOX(" and ")"
            part = box3D.split(',')
            p = part[0].split(' ')
            offset = [float(p[0]), float(p[1]), float(p[2])]

        return offset

    @classmethod
    def tile_geom_geojson(cls, city, offset, tile):
        """Returns a list of geometries in string representation.

        Parameters
        ----------
        city : str
        offset : list
            [x, y, z] as float
        tile : str
            '6/22/28'

        Returns
        -------
        res : list
            List of OrderedDict with a 'gid' and a 'geom' key.

            The 'geom' key is defined in geojson format such as
            '{"type":"", "bbox":"","coordinates":[[[[x0, y0, z0], ...]]]}'
        """

        sql = ("SELECT gid, ST_AsGeoJSON(ST_Translate(geom,"
               "{2},{3},{4}), 2, 1) AS geom from {0}"
               " WHERE quadtile='{1}'"
               .format(city, tile, -offset[0], -offset[1], -offset[2]))
        res = cls.query_asdict(sql)

        return res

    @classmethod
    def tile_geom_binary(cls, city, tile):
        """Returns a list of geometries in binary representation

        Parameters
        ----------
        city : str
        tile : str
            '6/22/28'

        Returns
        -------
        res : list
            List of OrderedDict with 'box3D' and 'binary' keys.
        """

        sql = ("SELECT Box3D(geom), ST_AsBinary(geom) as binary from {0}"
               " where quadtile='{1}'".format(city, tile))
        res = cls.query_asdict(sql)

        return res

    @classmethod
    def attribute_for_gid(cls, city, gid, attribute):
        """Returns a value for the attribute of the specific gid object

        Parameters
        ----------
        city : str
        gid : str
        attribute : str

        Returns
        -------
        val : str
        """

        sql = ("SELECT {0} FROM {1} WHERE gid = {2}"
               .format(attribute, city, gid))
        res = cls.query_asdict(sql)

        val = None
        if res:
            val = str(res[0][attribute])

        return val

    @classmethod
    def bbox_for_quadtiles(cls, city, quadtiles):
        """Returns a bbox for each quadtile in parameter

        Parameters
        ----------
        city : str
        quadtiles : list
            ["z0,y0,x0", "z1,y1,x1"]

        Returns
        -------
        res : list
            List of OrderedDict with 'bbox' and 'quadtile' keys.
        """

        cond = ""
        for quadtile in quadtiles:
            if cond:
                cond += " or "
            cond += "quadtile='{0}'".format(quadtile)

        sql = ('SELECT quadtile, bbox from {0}_bbox where {1}'
               .format(city, cond))

        return cls.query_asdict(sql)

    @classmethod
    def tiles_for_level(cls, city, level):
        """Returns tiles for the specific level

        Parameters
        ----------
        city : str
        level : int

        Returns
        -------
        res : list
            List of OrderedDict with 'quadtile' and 'bbox' as keys
        """

        sql = ("SELECT quadtile, bbox FROM {0}_bbox"
               " WHERE substr(quadtile,1,1)='{1}'"
               .format(city, level))
        return cls.query_asdict(sql)

    @classmethod
    def score_for_polygon(cls, city, pol, scoreFunction):
        """Returns scores

        Parameters
        ----------
        city : str
        poly : list
            ["x0 y0", "x1 y1", "x2 y2", "x3, y3"]
        scoreFunction : str

        Returns
        -------
        result : list
            List of dict whith 'score', 'gid' and 'box3d' keys
        """

        sql = ("SELECT gid, Box3D(geom), {0} as \"score\" FROM {1} "
               "WHERE (geom && 'POLYGON(({2}, {3}, {4}, {5}, {2}))'::geometry)"
               " ORDER BY score DESC"
               .format(scoreFunction, city, pol[0], pol[1], pol[2], pol[3]))

        return cls.query_asdict(sql)

    @classmethod
    def add_column(cls, city, column, typecol):
        """Adds a column in table

        Parameters
        ----------
        city : str
        column : str
        typecol : str

        Returns
        -------
        Nothing
        """

        sql = ("ALTER TABLE {0} ADD COLUMN {1} {2}"
               .format(city, column, typecol))
        cls.db.cursor().execute(sql)

    @classmethod
    def update_table(cls, city, quadtile, weight, gid):
        """Updates the table for a specific object

        Parameters
        ----------
        city : str
        quadtile : str
        weight : str
        gid : str

        Returns
        -------
        Nothing
        """

        sql = ("UPDATE {0} SET quadtile = '{1}', weight = {2} WHERE gid = {3}"
               .format(city, quadtile, weight, gid))
        cls.db.cursor().execute(sql)

    @classmethod
    def create_index(cls, city, column):
        """Creates an index on the column

        Parameters
        ----------
        city : str
        column : str

        Returns
        -------
        Nothing
        """

        sql = ("CREATE INDEX tileIdx_{0} on {0} ({1})"
               .format(city, column))
        cls.db.cursor().execute(sql)

    @classmethod
    def create_bbox_table(cls, city):
        """Creates the bbox city

        Parameters
        ----------
        city : str

        Returns
        -------
        Nothing
        """

        sql = ("CREATE TABLE {0}_bbox (quadtile varchar(10) PRIMARY KEY"
               ", bbox Box3D);".format(city))
        cls.db.cursor().execute(sql)

    @classmethod
    def insert_into_bbox_table(cls, city, quadtile, bbox):
        """Insert a new line in bbox table for the city

        Parameters
        ----------
        city : str
        quadtile : str
        bbox : str
            In linestring format

        Returns
        -------
        Nothing
        """

        sql = ("INSERT INTO {0}_bbox values ('{1}', "
               "Box3D(ST_GeomFromText('LINESTRING({2})')))"
               .format(city, quadtile, bbox))
        cls.db.cursor().execute(sql)

    @classmethod
    def drop_column(cls, city, column):
        """Drops a column in the table

        Parameters
        ----------
        city : str
        column : str

        Returns
        -------
        Nothing
        """

        sql = ("ALTER TABLE {0} DROP COLUMN IF EXISTS {1}"
               .format(city, column))
        cls.db.cursor().execute(sql)

    @classmethod
    def drop_bbox_table(cls, city):
        """Drops a table

        Parameters
        ----------
        city : str

        Returns
        -------
        Nothing
        """

        sql = ("DROP TABLE IF EXISTS {0}_bbox;".format(city))
        cls.db.cursor().execute(sql)

    @classmethod
    def query(cls, query, parameters=None):
        """Performs a query and yield results
        """
        cur = cls.db.cursor()
        cur.execute(query, parameters)
        if not cur.rowcount:
            return None
        for row in cur:
            yield row

    @classmethod
    def query_asdict(cls, query, parameters=None):
        """Iterates over results and returns namedtuples
        """
        return [
            line._asdict()
            for line in cls.query(query, parameters=parameters)
        ]

    @classmethod
    def query_aslist(cls, query, parameters=None):
        """Iterates over results and returns values in a flat list
        (usefull if one column only)
        """
        return list(chain(*cls.query(query, parameters=parameters)))

    @classmethod
    def init_app(cls, app):
        """
        Initialize db session lazily
        """
        cls.db = connect(
            "postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_NAME}"
            .format(**app.config),
            cursor_factory=NamedTupleCursor,
        )
        # autocommit mode for performance (we don't need transaction)
        cls.db.autocommit = True
