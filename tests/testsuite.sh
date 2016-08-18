#! /bin/sh

SCRIPT=`realpath $0`
SCRIPTPATH=`dirname $SCRIPT`

export PYTHONPATH=$PYTHONPATH:$SCRIPTPATH/..
nosetests $SCRIPTPATH/*.py
