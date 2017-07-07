# -*- coding: utf-8 -*-

from itertools import chain
from psycopg2 import connect, sql
from psycopg2.extras import NamedTupleCursor

from .utils import CitiesConfig

def table_to_sql(table):
    return sql.SQL('.').join([sql.Identifier(x) for x in table.split('.')])

class Session():
    """
    Session object used as a global connection object to the db

    # FIXME: handle disconnection
    """
    db = None

    @classmethod
    def offset(cls, city, tile):
        """Returns the center of a specific tile that can be used as an offset

        Parameters
        ----------
        city : str
        tile : int

        Returns
        -------
        offset : list
            [x, y, z] as float or None if no tile is found
        """

        query = sql.SQL("SELECT bbox from {0} WHERE tile = {1}").format(
            table_to_sql(CitiesConfig.tile_table(city)), sql.Literal(tile))
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
    def tile_geom_geojson(cls, city, offset, tile):
        """Returns a list of geometries in string representation.

        Parameters
        ----------
        city : str
        offset : list
            [x, y, z] as float
        tile : int

        Returns
        -------
        res : list
            List of OrderedDict with a 'gid' and a 'geom' key.

            The 'geom' key is defined in geojson format such as
            '{"type":"", "bbox":"","coordinates":[[[[x0, y0, z0], ...]]]}'
        """

        query = sql.SQL("SELECT {0}.gid AS box, ST_AsGeoJSON("
            "ST_Translate({0}.geom, {2},{3},{4})) AS geom FROM {0} INNER JOIN"
            " {1} ON {0}.gid={1}.feature WHERE {1}.tile={5}").format(
                table_to_sql(CitiesConfig.geometry_table(city)),
                table_to_sql(CitiesConfig.feature_table(city)),
                sql.Literal(-offset[0]), sql.Literal(-offset[1]),
                sql.Literal(-offset[2]), sql.Literal(tile))
        res = cls.query_asdict(query)

        return res

    @classmethod
    def tile_geom_binary(cls, city, tile, offset):
        """Returns a list of geometries in binary representation

        Parameters
        ----------
        city : str
        offset : list
            [x, y, z] as float
        tile : int

        Returns
        -------
        res : list
            List of OrderedDict with 'box3D' and 'binary' keys.
        """

        query = sql.SQL("SELECT Box3D({0}.geom) AS box, ST_AsBinary("
            "ST_Translate({0}.geom, {2},{3},{4})) AS geom FROM {0} INNER JOIN"
            " {1} ON {0}.gid={1}.feature WHERE {1}.tile={5}").format(
                table_to_sql(CitiesConfig.geometry_table(city)),
                table_to_sql(CitiesConfig.feature_table(city)),
                sql.Literal(-offset[0]), sql.Literal(-offset[1]),
                sql.Literal(-offset[2]), sql.Literal(tile))

        query = "WITH t AS (SELECT ST_Collect(ST_Translate(surface_geometry.geometry, {2},{3},{4})) AS geom FROM surface_geometry join thematic_surface on surface_geometry.root_id=thematic_surface.lod2_multi_surface_id join {0} on thematic_surface.building_id={0}.feature where {0}.tile={1} and surface_geometry.geometry is not null group by surface_geometry.root_id) SELECT Box3D(geom) AS box, ST_AsBinary(geom) as geom FROM t".format(CitiesConfig.feature_table(city), tile, -offset[0], -offset[1], -offset[2])
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
    def get_all_tiles(cls, city):
        """Returns all tiles defined in the database

        Parameters
        ----------
        city : str

        Returns
        -------
        res : list
            List of OrderedDict with 'tile' and 'bbox' as keys
        """

        query = sql.SQL("SELECT tile, bbox FROM {0}").format(
                table_to_sql(CitiesConfig.tile_table(city)))
        return cls.query_asdict(query)

    @classmethod
    def get_hierarchy(cls, city):
        """Returns the tile hierarchy defined in the database

        Parameters
        ----------
        city : str

        Returns
        -------
        res : list
            List of OrderedDict with 'tile' and 'child' as keys
        """

        query = sql.SQL("SELECT tile, child FROM {0}").format(
                table_to_sql(CitiesConfig.hierarchy_table(city)))
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

        polygon = "POLYGON(({0}, {1}, {2}, {3}, {0}))".format(
                  pol[0], pol[1], pol[2], pol[3])
        query = sql.SQL("SELECT gid, Box3D(geom), {0} as \"score\" FROM {1} "
                "WHERE (geom && {2}::geometry) ORDER BY score DESC").format(
                sql.SQL(scoreFunction),
                table_to_sql(CitiesConfig.geometry_table(city)),
                sql.Literal(polygon))

        query = "select cityobject.id as gid, Box3D(cityobject.envelope), ST_Area(Box2D(cityobject.envelope)) as score from cityobject inner join building on cityobject.id=building.id where (St_centroid(cityobject.envelope) && '{2}'::geometry) order by score desc".format(scoreFunction, CitiesConfig.geometry_table(city), polygon)

        return cls.query_asdict(query)

    @classmethod
    def create_hierarchy_tables(cls, city):
        """Creates the tables used to store the city organisation

        Parameters
        ----------
        city : str

        Returns
        -------
        Nothing
        """

        cursor = cls.db.cursor()
        tileTable = CitiesConfig.tile_table(city)
        featureTable = CitiesConfig.feature_table(city)
        hierarchyTable = CitiesConfig.hierarchy_table(city)

        # Create tables
        query = sql.SQL("CREATE TABLE {0} (tile integer PRIMARY KEY"
               ", bbox Box3D);").format(table_to_sql(tileTable))
        cursor.execute(query)

        query = sql.SQL("CREATE TABLE {0} (tile integer, child integer,"
                        "PRIMARY KEY(tile, child));").format(
                        table_to_sql(hierarchyTable))
        cursor.execute(query)

        query = sql.SQL("CREATE TABLE {0} (feature integer PRIMARY KEY"
               ", tile integer);").format(table_to_sql(featureTable))
        cursor.execute(query)

        # Create index
        # TODO: take schema into account for index name?
        query = sql.SQL("CREATE INDEX {0} on {1} (tile)").format(
                sql.Identifier(hierarchyTable.replace(".", "") + "idx"),
                table_to_sql(hierarchyTable))
        cls.db.cursor().execute(query)

    @classmethod
    def insert_tile(cls, city, tileId, bbox):
        """Insert a new line in the tile table for the city

        Parameters
        ----------
        city : str
        tileId : int
        bbox : str
            In linestring format

        Returns
        -------
        Nothing
        """

        bboxString = "LINESTRING({0})".format(bbox)
        query = sql.SQL("INSERT INTO {0} values ({1}, Box3D(ST_GeomFromText({2})))").format(
                table_to_sql(CitiesConfig.tile_table(city)),
                sql.Literal(tileId), sql.Literal(bboxString))
        cls.db.cursor().execute(query)

    @classmethod
    def insert_feature(cls, city, featureId, tileId):
        """Insert a new line in the tile table for the city

        Parameters
        ----------
        city : str
        featureId : int
        tileId : int

        Returns
        -------
        Nothing
        """

        query = sql.SQL("INSERT INTO {0} values ({1}, {2})").format(
               table_to_sql(CitiesConfig.feature_table(city)),
               sql.Literal(featureId), sql.Literal(tileId))
        cls.db.cursor().execute(query)

    @classmethod
    def insert_hierarchy(cls, city, tree):
        """Insert a tree in the hierarchy table

        Parameters
        ----------
        city : str
        tree : dict

        Returns
        -------
        Nothing
        """

        def recurse(tile):
            (tileId, children) = tile
            for child in children:
                query = sql.SQL("INSERT INTO {0} values ({1}, {2})").format(
                        table_to_sql(CitiesConfig.hierarchy_table(city)),
                        sql.Literal(tileId), sql.Literal(child[0]))
                cls.db.cursor().execute(query)
                recurse(child)

        recurse(tree)

    @classmethod
    def drop_hierarchy_tables(cls, city):
        """Drops the tables organising the data

        Parameters
        ----------
        city : str

        Returns
        -------
        Nothing
        """

        cursor = cls.db.cursor()

        query = sql.SQL("DROP TABLE IF EXISTS {0}").format(
                table_to_sql(CitiesConfig.tile_table(city)))
        cursor.execute(query)

        query = sql.SQL("DROP TABLE IF EXISTS {0}").format(
                table_to_sql(CitiesConfig.feature_table(city)))
        cursor.execute(query)

        query = sql.SQL("DROP TABLE IF EXISTS {0}").format(
                table_to_sql(CitiesConfig.hierarchy_table(city)))
        cursor.execute(query)

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
