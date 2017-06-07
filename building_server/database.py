# -*- coding: utf-8 -*-

from itertools import chain
from psycopg2 import connect
from psycopg2.extras import NamedTupleCursor
from psycopg2 import sql

from .utils import CitiesConfig


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

        query = ("SELECT bbox from {0}_bbox WHERE quadtile = '{1}'"
               .format(CitiesConfig.table(city), tile))
        res = cls.query_aslist(query)

        offset = None
        if res:
            o = res[0]
            box3D = o[6:len(o)-1]   # remove "BOX(" and ")"
            part = box3D.split(',')
            p = part[0].split(' ')
            offset = [float(p[0]), float(p[1]), float(p[2])]

        return offset

    @classmethod
    def tile_center(cls, city, tile, layer, representation):
        rep = CitiesConfig.representation(city, layer, representation)
        table = rep["featuretable"]
        featureTable = CitiesConfig.featureTable(city, layer)
        query = ("WITH t AS (SELECT gid FROM {1} WHERE tile='{2}')"
               "SELECT Box3D(geom) FROM {0} JOIN t ON {0}.gid=t.gid"
               .format(table, featureTable, tile))
        res = cls.query_aslist(query)

        center = None
        if res:
            o = res[0]
            box3D = o[6:len(o)-1]   # remove "BOX3D(" and ")"
            part = box3D.split(',')
            p1 = part[0].split(' ')
            p2 = part[1].split(' ')
            center = [
                (float(p1[0]) + float(p2[0])) / 2,
                (float(p1[1]) + float(p2[1])) / 2,
                (float(p1[2]) + float(p2[2])) / 2 ]

        return center

    @classmethod
    def feature_center(cls, city, gid, layer, representation):
        rep = CitiesConfig.representation(city, layer, representation)
        query = "SELECT Box3D(geom) FROM {0} WHERE gid={1}".format(rep["featuretable"], gid)
        res = cls.query_aslist(query)

        center = None
        if res:
            o = res[0]
            box3D = o[6:len(o)-1]   # remove "BOX3D(" and ")"
            part = box3D.split(',')
            p1 = part[0].split(' ')
            p2 = part[1].split(' ')
            center = [
                (float(p1[0]) + float(p2[0])) / 2,
                (float(p1[1]) + float(p2[1])) / 2,
                (float(p1[2]) + float(p2[2])) / 2 ]

        return center

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

        query = ("SELECT gid, ST_AsGeoJSON(ST_Translate(geom,"
               "{2},{3},{4}), 2, 1) AS geom from {0}"
               " WHERE quadtile='{1}'"
               .format(CitiesConfig.table(city), tile, -offset[0], -offset[1],
                       -offset[2]))
        res = cls.query_asdict(query)

        return res

    @classmethod
    def feature_polyhedral(cls, city, offset, feature, layer, representation):
        """Returns a list of geometries in binary form.

        Parameters
        ----------
        city : str
        offset : list
            [x, y, z] as float
        feature : int
        layer : str
            'buildings'
        representation : str
            'lod1'

        Returns
        -------
        res : list
            List of OrderedDict with a 'gid' (or 'tile' if not feature) and a 'geom' key.

            The 'geom' key is defined in binary wkb format.
        """

        rep = CitiesConfig.representation(city, layer, representation)
        table = rep["featuretable"]
        query = ("SELECT gid, ST_AsBinary(ST_Translate(geom,"
        "{2},{3},{4})) AS geom, Box3D(ST_Translate(geom,"
        "{2},{3},{4})) AS box FROM {0} WHERE gid={1}"
        .format(table, feature, -offset[0], -offset[1],
                -offset[2]))

        res = cls.query_asdict(query)

        return res

    @classmethod
    def tile_polyhedral(cls, city, offset, tile, isFeature, layer, representation, without, onlyTiles):
        """Returns a list of geometries in binary form.

        Parameters
        ----------
        city : str
        offset : list
            [x, y, z] as float
        tile : int
        isFeature : boolean
        layer : str
            'buildings'
        representation : str
            'lod1'

        Returns
        -------
        res : list
            List of OrderedDict with a 'gid' (or 'tile' if not feature) and a 'geom' key.

            The 'geom' key is defined in binary wkb format.
        """

        rep = CitiesConfig.representation(city, layer, representation)
        if isFeature:
            # TODO optimise
            table = rep["featuretable"]
            featureTable = CitiesConfig.featureTable(city, layer)
            query = ("WITH t AS (SELECT gid FROM {1} WHERE tile='{2}')"
            "SELECT {0}.gid, ST_AsBinary(ST_Translate(geom,"
            "{3},{4},{5})) AS geom, Box3D(ST_Translate(geom,"
            "{3},{4},{5})) AS box from {0} JOIN t ON {0}.gid=t.gid"
            .format(table, featureTable, tile, -offset[0], -offset[1],
                    -offset[2]))
        else:
            table = rep["tiletable"]
            query = ("SELECT tile, ST_AsBinary(ST_Translate(geom,"
                   "{2},{3},{4})) AS geom, Box3D(ST_Translate(geom,"
                   "{2},{3},{4})) AS box from {0}"
                   " WHERE tile={1}"
                   .format(table, tile, -offset[0], -offset[1],
                           -offset[2]))

        res = cls.query_asdict(query)

        return res

    @classmethod
    def tile_2_5D(cls, city, offset, tile, isFeature, layer, representation, without, onlyTiles):
        """Returns a list of geometries in string representation.

        Parameters
        ----------
        city : str
        offset : list
            [x, y, z] as float
        tile : int
        isFeature : boolean
        layer : str
            'buildings'
        representation : str
            'lod1'

        Returns
        -------
        res : list
            List of OrderedDict with a 'gid' (or 'tile'), 'zmin', 'zmax' and a 'geom' key.

            The 'geom' key is defined in geojson format such as
            '{"type":"", "bbox":"","coordinates":[[[[x0, y0, z0], ...]]]}'
        """

        rep = CitiesConfig.representation(city, layer, representation)
        if isFeature:
            # TODO optimise
            table = cls.table_to_sql(rep["featuretable"])
            featureTable = cls.table_to_sql(CitiesConfig.featureTable(city, layer))
            condition = sql.SQL("tile='{0}'").format(sql.Literal(tile))
            if without is not None:
                subCondition = sql.SQL(" OR ").join([sql.SQL("gid!={0}").format(sql.Literal(f)) for f in without.split(",")])
                condition = sql.SQL("{0} AND {1}").format(condition, subCondition)
            query = sql.SQL("WITH t AS (SELECT gid FROM {1} WHERE {2})"
                   "SELECT {0}.gid, zmin, zmax, ST_AsGeoJSON(geom,"
                   "2, 1) AS geom from {0} JOIN t ON {0}.gid=t.gid"
                   ).format(table, featureTable, condition)
        else:
            table = cls.table_to_sql(rep["tiletable"])
            geomSelection = sql.SQL("geom")
            tables = table
            subqueries = []
            if without is not None:
                featureTable = cls.table_to_sql(CitiesConfig.featureTable(city, layer))
                geomSelection = sql.SQL("ST_Multi(ST_Difference({0}, feature_fp))").format(geomSelection)
                tables = sql.SQL("{0}, t").format(table)
                condition = sql.SQL(" OR ").join([sql.SQL("gid={0}").format(sql.Literal(f)) for f in without.split(",")])
                subquery = sql.SQL("t AS (SELECT ST_Union(footprint) "
                            "AS feature_fp FROM {0} WHERE {1})"
                            ).format(featureTable, condition)
                subqueries.append(subquery)
            if onlyTiles is not None:
                tileTable = cls.table_to_sql(CitiesConfig.tileTable(city))
                geomSelection = sql.SQL("ST_Multi(ST_Intersection({0}, tile_fp))").format(geomSelection)
                tables = sql.SQL("{0}, d").format(table)
                condition = sql.SQL(" OR ").join([sql.SQL("tile={0}").format(sql.Literal(t)) for t in onlyTiles.split(",")])
                subquery = sql.SQL("d AS (SELECT ST_Union(footprint) "
                            "AS tile_fp FROM {0} WHERE {1})"
                            ).format(tileTable, condition)
                subqueries.append(subquery)
            query = sql.SQL("SELECT tile, zmin, zmax, ST_AsGeoJSON({0}, 2, 1) AS geom "
                    "FROM {1} WHERE tile={2}"
                    ).format(geomSelection, tables, sql.Literal(tile))
            if len(subqueries) != 0:
                query = sql.SQL("WITH {0} {1}").format(sql.SQL(", ").join(subqueries), query)

        res = cls.query_asdict(query)
        res = [t for t in res if t['geom'] != None]

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

        query = ("SELECT Box3D(geom), ST_AsBinary(geom) as binary from {0}"
               " where quadtile='{1}'".format(CitiesConfig.table(city), tile))
        res = cls.query_asdict(query)

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

        query = ("SELECT {0} FROM {1} WHERE gid = {2}"
               .format(attribute, CitiesConfig.table(city), gid))
        res = cls.query_asdict(query)

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

        query = ('SELECT quadtile, bbox from {0}_bbox where {1}'
               .format(CitiesConfig.table(city), cond))

        return cls.query_asdict(query)

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

        regex = "{0}/".format(level)

        query = ("SELECT quadtile, bbox FROM {0}_bbox"
               " WHERE substr(quadtile,1,{1})='{2}'"
               .format(CitiesConfig.table(city), len(regex), regex))
        return cls.query_asdict(query)

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

        query = ("SELECT gid, Box3D(geom), {0} as \"score\" FROM {1} "
               "WHERE (geom && 'POLYGON(({2}, {3}, {4}, {5}, {2}))'::geometry)"
               " ORDER BY score DESC"
               .format(scoreFunction, city, pol[0], pol[1], pol[2], pol[3]))

        return cls.query_asdict(query)

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

        query = ("ALTER TABLE {0} ADD COLUMN {1} {2}"
               .format(CitiesConfig.table(city), column, typecol))
        cls.db.cursor().execute(query)

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

        query = ("UPDATE {0} SET quadtile = '{1}', weight = {2} WHERE gid = {3}"
               .format(CitiesConfig.table(city), quadtile, weight, gid))
        cls.db.cursor().execute(query)

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

        query = ("CREATE INDEX tileIdx_{0} on {1} ({2})"
               .format(CitiesConfig.table(city).replace(".", ""), city,
                       column))
        cls.db.cursor().execute(query)

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

        query = ("CREATE TABLE {0}_bbox (quadtile varchar(10) PRIMARY KEY"
               ", bbox Box3D);".format(CitiesConfig.table(city)))
        cls.db.cursor().execute(query)

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

        query = ("INSERT INTO {0}_bbox values ('{1}', "
               "Box3D(ST_GeomFromText('LINESTRING({2})')))"
               .format(CitiesConfig.table(city), quadtile, bbox))
        cls.db.cursor().execute(query)

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

        query = ("ALTER TABLE {0} DROP COLUMN IF EXISTS {1}"
               .format(CitiesConfig.table(city), column))
        cls.db.cursor().execute(query)

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

        query = ("DROP TABLE IF EXISTS {0}_bbox;"
               .format(CitiesConfig.table(city)))
        cls.db.cursor().execute(query)


    @classmethod
    def table_to_sql(cls, table):
        return sql.SQL('.').join([sql.Identifier(x) for x in table.split('.')])

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
