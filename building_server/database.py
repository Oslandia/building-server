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
