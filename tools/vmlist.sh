#!/bin/bash

for i in `nova hypervisor-list | grep -v "^+" | grep -v Hypervisor | awk '{print $4}'`; do
    echo "+++++ ${i}"
    echo ""
    nova list --all-tenants --host ${i} | grep -v "+----" | grep -v "| ID"
    echo ""
done
