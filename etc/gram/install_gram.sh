#!/bin/bash

# Install GRAM on either compute or control node

export SENSE="control"

if [ $# -gt 0 ]
then
    export SENSE=$1
fi

# This seems not to get set early enough in some circumstances...
mkdir -p /etc/quantum

# Set up the install shell scripts based on the parameters specified
# in /etc/gram/config.json
cd ~gram/gram/src/install
export PYTHONPATH=$PYTHONPATH:~gram/gram/src
python OpenStack.py
cd /tmp/install
chmod a+x *.sh
./install_$SENSE.sh

# Start up gram on the control node
if [ $SENSE = "control" ]
then
    /etc/gram/install_gram_services.sh
    /etc/gram/gram_services.sh start
fi




