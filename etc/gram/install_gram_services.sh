#!/bin/bash

# Install all GRAM services

export PYTHONPATH=/home/gram/gram/src:.

# First, change the conf files for the current configuration
for service in gram-am gram-amv2
do
    python modify_conf_env.py /home/gram/gram/src/services/$service.conf OS_TENANT_NAME os_tenant_name env | sh
    python modify_conf_env.py /home/gram/gram/src/services/$service.conf OS_USERNAME os_username env | sh
    python modify_conf_env.py /home/gram/gram/src/services/$service.conf OS_PASSWORD os_password env | sh
    python modify_conf_env.py /home/gram/gram/src/services/$service.conf SERVICE_TOKEN service_token env | sh
done

# Then copy the modified file into /etc/init and make the link in /etc/init.d
for service in gram-am gram-amv2 gram-ch gram-cni gram-ctrl gram-vmoc
do
    echo "Installing service $service"
    cp /home/gram/gram/src/services/$service.conf /etc/init
    ln -fs /etc/init.d/$service /lib/init/upstart-job
done

