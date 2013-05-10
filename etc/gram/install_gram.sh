#!/bin/bash

# Install GRAM on either compute or control node

export SENSE="control"

if [ $# -gt 0 ]
then
    export SENSE=$1
fi

# Align the owner id of gram for the packages we've read in
chown -R gram.gram ~gram /etc/gram

# This seems not to get set early enough in some circumstances...
mkdir -p /etc/quantum

# Set up certificates
mkdir /etc/gram/certs
/opt/gcf/src/gen-certs.py --notAll --ch --am --directory=/etc/gram/certs
chown -R gram.gram /etc/gram/certs


# Set up the install shell scripts based on the parameters specified
# in /etc/gram/config.json
cd ~gram/gram/src/install
export PYTHONPATH=~gram/gram/src:$PYTHONPATH
python OpenStack.py
cd /tmp/install
chmod a+x *.sh
./install_$SENSE.sh

# Control-node specific logic 
if [ $SENSE = "control" ]
then
    # Change the 'host' entry in .gcf/gcf_config to fit the configuration
    python /etc/gram/modify_conf_env.py ~/.gcf/gcf_config host control_host "" | sh

    # Install gram_ssh_proxy
    cd ~gram/gram/src/gram/am/gram
    make gram_ssh_proxy

    # Install and start up gram on the control node
    /etc/gram/install_gram_services.sh
    /etc/gram/gram_services.sh start
fi




