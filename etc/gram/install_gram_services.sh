#!/bin/bash

# Install all GRAM services

for service in gram-am gram-amv2 gram-ch gram-cni gram-ctrl gram-vmoc
do
    echo "Installing service $service"
    cp /home/gram/gram/src/services/$service.conf /etc/init
    ln -s /etc/init.d/$service /lib/init/upstart-job
done

