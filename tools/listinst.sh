#!/bin/bash

for x in `nova hypervisor-list | grep -v "^+" | grep -v Hypervisor | awk '{print $4}'`; do 

    echo "Host ${x}"
    vmlist=`nova list --all-tenants --host ${x} | awk '{print $2}'`

    for i in $vmlist; do 
        if [ "$i" == "ID" ]; then
            continue
        fi
        instid=`nova show $i | grep instance_name | awk '{print $4}'` 
        vmname=`nova show $i | grep '| name' | awk '{print $4}'` 
        echo "$i  $vmname  $instid"
    done
done
