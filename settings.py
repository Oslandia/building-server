DB_INFOS = {
    "host": "localhost",
	"dbname": "lyon",
	"user": "jeremy",
	"password": "jeremy",
	"port": "5432"
}

CITIES = {
	"lyon": {
		"tablename": "lyongeom",
		"extent": [[1837816.94334,5170036.4587], [1847692.32501,5178412.82698]],
		"maxtilesize": 2000,
		"srs":"EPSG:3946",
		"attributes":[],
		"featurespertile":20
	},
	"lyon_lod1": {
		"tablename": "lod1",
		"extent": [[1837816.94334,5170036.4587], [1847692.32501,5178412.82698]],
		"maxtilesize": 2000,
		"srs":"EPSG:3946",
		"attributes":[],
		"featurespertile":50
	},
	"lyon_lod2": {
		"tablename": "split",
		"extent": [[1837816.94334,5170036.4587], [1847692.32501,5178412.82698]],
		"maxtilesize": 2000,
		"srs":"EPSG:3946",
		"attributes":["height"],
		"featurespertile":50
	},
	"test": {
		"tablename": "test",
		"extent": [[0,0], [2000, 1000]],
		"maxtilesize": 500,
		"srs":"EPSG:3946",
		"attributes":[],
		"featurespertile":2
	}
}