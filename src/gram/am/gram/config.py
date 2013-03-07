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


import logging

# OpenStack related configuration
#default_VM_flavor = 'm1.small'  
default_VM_flavor = 'm1.smaller'  
#default_VM_flavor = 'm1.tiny'  

#default_OS_image = 'cirros-0.3.1'
#default_OS_image = 'cirros-2nic-x86_64'
#default_OS_image = 'cirros-4nic'
#default_OS_type = 'Linux'
#default_OS_version = '0.3'

#default_OS_image = 'f18-x86_64-openstack-sda'
#default_OS_type = 'Linux'
#default_OS_version = '17'

default_OS_image = 'ubuntu-12.04'
#default_OS_image = 'ubuntu-12.04-2nic'
#default_OS_image = 'ubuntu-2nic-wkey'
default_OS_type = 'Linux'
default_OS_version = '12'

external_router_name = 'externalRouter'

tenant_admin_pwd = 'sliceMaster:-)'  # Password for the tenant's admin user
                                  # account


# GENI interface related configuration
default_execute_shell = 'sh'   # default shell to use for use by execute
                               # services specified in the request rspec
sliver_urn_prefix = 'urn:publicid:IDN+gram+sliver+'
vm_urn_prefix = sliver_urn_prefix + 'vm+'
interface_urn_prefix = sliver_urn_prefix + 'interface+'
link_urn_prefix = sliver_urn_prefix + 'link+'

allocation_expiration_minutes =  10      # allocations expire in 10 mins
lease_expiration_minutes =  7 * 24 * 60  # resources can be leased for 7 days

# Allocation states for slivers
unallocated = 'geni_unallocated'
allocated = 'geni_allocated'
provisioned = 'geni_provisioned'

# Operational states for slivers
notready = 'geni_notready'
configuring = 'geni_configuring'
ready = 'geni_ready'
failed = 'geni_failed'


# Error codes returned by this aggregate manager
# GENI standard codes.
SUCCESS = 0
REQUEST_PARSE_FAILED = 1        # aka BADARGS
UNKNOWN_SLICE = 12              # aka SEARCHFAILED
UNSUPPORTED = 13                
SLICE_ALREADY_EXISTS = 17       # aka ALREADYEXISTS
OUT_OF_RANGE = 19               # typically for time mismatches

# GRAM specific codes

# Aggregate Manager software related configuration
logger = logging.getLogger('gcf.am3.gram')

# Parameters regarding archiving/restoration of GRAM aggregste state
gram_snapshot_directory = '/etc/gram/snapshots' # Directory of snapshots
recover_from_snapshot = None # Specific file from which to recover 
recover_from_most_recent_snapshot = True # Should we restore from most recent
snapshot_maintain_limit = 10 # Remove all snapshots earlier than this #

# File where GRAM stores the subnet number for the last allocated sub-net
# This is used in resources.py.  This file is temporary.  It should not be
# needed when we have namespaces working.
subnet_numfile = '/etc/gram/GRAM-next-subnet.txt'

# File where GRAM stores the SSH proxy port state table, and its assoicated
# lock file. These files are used in manage_ssh_proxy.py
port_table_file = '/etc/gram/gram-ssh-port-table.txt'
port_table_lock_file = '/etc/gram/gram-ssh-port-table.lock'

# Location of the GRAM SSH proxy utility binary, which enables GRAM
# to create and delete proxies for each user requested VM
ssh_proxy_exe = '/usr/local/bin/gram_ssh_proxy'

# GRAM AM URN (Component ID of AM)
gram_am_urn = ''

# PORT on which to communicate with compute_node_interace
compute_node_interface_port = 9501

# PORT on which to communicate to VMOC interface manager
vmoc_interface_port = 7001

# Should GRAM automatically register slices with VMOC?
vmoc_slice_autoregister = True # Set to False to disable GRAM/VMOC interface

# Variables for VMOC/GRAM switch behavior/configuration
vmoc_set_vlan_on_untagged_packet_out = False
vmoc_set_vlan_on_untagged_flow_mod = True
vmoc_accept_clear_all_flows_on_startup = True

# Maps disk_image by name to dic with {os, version, description}
disk_image_metadata = {}

import json
import sys
# Read in configuration file
# For each key in JSON dictionary read
# Try to set the associated value in config module
# if it can be coerced into the object of current type
def initialize(config_file):
    print "config.initialize: " + config_file

    data = None
    try:
        f = open(config_file, 'r')
        data = f.read()
        f.close()
    except Exception, e:
        print "Failed to read GRAM config file: " + config_file + str(e)
        logger.info("Failed to read GRAM config file: " + config_file)
        return

    config_module = sys.modules[__name__]
    data_json = json.loads(data)

    for var in data_json.keys():
        if var[:2] == "__": continue # Comment in the JSON file
        if not hasattr(config_module, var):
            logger.info("No variable named " + var + " in module config")
        else:
            current_type = type(getattr(config_module, var)).__name__
            new_value = data_json[var]
            new_type = type(new_value).__name__
            can_coerce = True

            try :
                if current_type == new_type:
                    pass
                elif current_type == 'int':
                    new_value = int(new_value)
                elif current_type == 'long':
                    new_value = long(new_value)
                elif current_type == 'str':
                    new_value = str(new_value)
                elif current_type == 'float':
                    new_value = float(new_value)
                elif current_type == 'bool':
                    new_value = bool(new_value)
                else:
                    logger.info("Can't coerce type " + current_type + " to " + 
                                new_type)
                    can_coerce = False
            except Exception, e:
                logger.info("Error coercing value : " + new_value + \
                                "to " + current_type)
                can_coerce = False

            if can_coerce:
                setattr(config_module, var, new_value)

            
                    
    

