#!/usr/bin/python

import json
import sys

from vmoc.VMOCConfig import VMOCSliceConfiguration, VMOCVLANConfiguration

# Usage register_controller.sh slice [vlan controller ....] [unregister]

if len(sys.argv) < 2:
    print "Usage: register_controller.py slice [vlan controller ...] [unregister]"
    sys.exit()

print sys.argv[1]
print sys.argv[2]

slice_id = sys.argv[1]
vlan_controllers = json.loads(sys.argv[2])
vlan_configs = []
for i in range(len(vlan_controllers)):
    if i == 2*(i/2):
        vlan_tag = vlan_controllers[i]
        controller_url = vlan_controllers[i+1]
        vlan_config = \
            VMOCVLANConfiguration(vlan_tag=vlan_tag, \
                                      controller_url=controller_url)
        vlan_configs.append(vlan_config)

slice_config = \
    VMOCSliceConfiguration(slice_id=slice_id, vlan_configs=vlan_configs)

unregister = False
if len(sys.argv)>3: 
    unregister = bool(sys.argv[3])

print str(slice_config)

command = 'register'
if unregister: command = 'unregister'

command = command + " " + json.dumps(slice_config.__attr__())

print command


