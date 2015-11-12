# Building server

This is a prototype for a simple WFS server that retrieves polyhedral surfaces from a POSTGIS database and sends them back in a glTF file.

## Installation

### Python configuration

The server uses python 2.

Install the necessary modules :
```
easy_install cython
easy_install numpy
easy_install triangle
sudo apt-get install python-psycopg2
```

### Apache configuration

Install the apache wsgi module :
```
sudo apt-get install libapache2-mod-wsgi
```

In the apache site configuration file add the following lines :

```
WSGIPythonPath /*path_to_building_server*/
```

```
WSGIScriptAlias /server /*path_to_building_server*/server.py

<Directory /*path_to_building_server*/>
	Order allow,deny
	Allow from all
</Directory>
```

## Configuration

Modify the settings.py file to match your postgres configuration.
