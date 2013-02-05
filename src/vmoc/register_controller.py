#!/usr/bin/python

#----------------------------------------------------------------------
# Copyright (c) 2013 Raytheon BBN Technologies
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and/or hardware specification (the "Work") to
# deal in the Work without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Work, and to permit persons to whom the Work
# is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Work.
#
# THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER DEALINGS
# IN THE WORK.
#----------------------------------------------------------------------


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


