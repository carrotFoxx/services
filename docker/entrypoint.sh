#!/bin/bash -eu
if [ $1 == '--help' ]
then
    ls -al /opt/app/apps
fi

exec python3 /opt/app/apps/${1}.py --debug 0
