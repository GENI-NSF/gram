#!/bin/bash

# Install GRAM on either compute or control node

export SENSE="control"

if [ $# -gt 0 ]
then
    export SENSE=$1
fi

mkdir -p /etc/quantum
rm -f /etc/apt/sources.list.d/folsom.list
echo "deb http://ubuntu-cloud.archive.canonical.com/ubuntu precise-updates/folsom main" > /etc/apt/sources.list.d/folsom.list
apt-get install -f
apt-get update && apt-get dist-upgrade
cd ~gram/gram/src/install
export PYTHONPATH=$PYTHONPATH:~gram/gram/src
python OpenStack.py
cd /tmp/install
chmod a+x *.sh
./install_$SENSE.sh

if [ $SENSE = "control" ]
then
    /etc/gram/gram_services.sh start
fi




