import building_server
from building_server.server import GetGeometry
from building_server.server import GetCity
from building_server.database import Session
from multiprocessing import Pool

import argparse
import json
import re
import os

parser = argparse.ArgumentParser(description = 'Scrap all the building_server data. This script creates a folder per city in the current directory. These directory will contain all the city geometries and a tileset.json referencing them.')
parser.add_argument('city', help='city to download')
parser.add_argument('out_folder', help='city to download')
parser.add_argument('--jobs', type=int, help='parallel', default=1)
parser.add_argument('--tileset', help='read tileset')

args = parser.parse_args()

app = building_server.create_app()

out_folder = args.out_folder + '/' + args.city

to_download = []

def extract_urls(jsonFrag):
    if 'url' in jsonFrag:
        url = jsonFrag['url']

        tile = url[len('geometries/'):].split('/')

        destDir = out_folder + '/geometries/' + '/'.join(tile[:-1])
        destFile = destDir + '/' + tile[-1]
        os.makedirs(destDir, exist_ok=True)

        to_download.append({'url': url, 'file': destFile})

def download_one(task):
    with open(task['file'], 'wb') as f:
        tile = task['url'][len('geometries/'):]
        f.write(building_server.server.GetGeometry().run({'city': args.city, 'tile': tile, 'format': None}).data)

    return 0

os.makedirs(out_folder, exist_ok=True)

# tileset.json
print('Reading tileset.json...')
tileset = building_server.server.GetCity().run({'city': args.city}).data.decode()

# patch url
print('Patching tileset.json...')
tileset = re.sub(r'getGeometry\?[a-z]*=[^\&]*&tile=([0-9]*/[0-9]*/[0-9]*)&format=[a-z0-9]*', r'geometries/\1', tileset)

print('Writing tileset.json...')
with open(out_folder + '/tileset.json', 'w') as f:
    f.write(tileset)

print('Extracting urls...')
json.loads(tileset, object_hook=extract_urls)

pool = Pool(processes=args.jobs, initializer=Session.init_app, initargs=[app])

print('Extracting {} tiles using {} processes...'.format(len(to_download), args.jobs))
pool.map(download_one, to_download)

print('Done')


