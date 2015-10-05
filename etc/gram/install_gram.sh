#!/bin/bash

# Install GRAM on either compute or control node
# usage: install_gram <compute/control/network> <grizzly/juno>

export SENSE="control"
export OPENSTACKV="juno"

if [ $# -eq 1 ]
then
    export SENSE=$1
fi

if [ $# -eq 2 ]
then
    export OPENSTACKV=$2
fi

mkdir /home/gram/.backup

# Align the owner id of gram for the packages we've read in
chown -R gram.gram ~gram /etc/gram

# This seems not to get set early enough in some circumstances...
if [ $OPENSTACKV = "grizzly" ]
then
    mkdir -p /etc/quantum
else
    mkdir -p /etc/neutron
fi


# Set up the install shell scripts based on the parameters specified
# in /etc/gram/config.json
cd ~gram/gram/$OPENSTACKV/install
export PYTHONPATH=~gram/gram/src:~gram/gram/$OPENSTACKV:$PYTHONPATH
python OpenStack.py
cd /tmp/install
chmod a+x *.sh
#./install_$SENSE.sh

# Control-node specific logic 
if [ $SENSE = "control" ]
then
    # set up certs
    mkdir /etc/gram/certs
    /opt/gcf/src/gen-certs.py --notAll --ch --am --directory=/etc/gram/certs
    chown -R gram.gram /etc/gram/certs

    # Change the 'host' entry in .gcf/gcf_config to fit the configuration
    python /etc/gram/modify_conf_env.py ~/.gcf/gcf_config host control_host "" | sh

    # Install gram_ssh_proxy
    cd ~gram/gram/src/gram/am/gram
    # Force rebuild and reinstall in case there's an already built version around
    make -B gram_ssh_proxy

    # Install and start up gram on the control node
    /etc/gram/install_gram_services.sh
    /etc/gram/gram_services.sh start
fi


