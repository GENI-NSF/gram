#!/bin/bash

export SENSE="control"

if [ $# -gt 0 ]
then
    export SENSE=$1
fi

/etc/gram/gram_services.sh stop
dpkg --purge gram
cd /tmp/install
./uninstall_$SENSE.sh

