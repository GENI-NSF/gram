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


import sys
import time

import config
import open_stack_interface
import manage_ssh_proxy
import optparse

parser = optparse.OptionParser()
parser.add_option("--config", help="JSON config file",
                  default="/etc/gram/config.json")

[opts, slices] = parser.parse_args()

if len(slices) < 1 :
    print 'Usage: cleanup [--config configfile] <slicename>...<slicename>'
    sys.exit(0)

config.initialize(opts.config)

tenant_pwd = config.tenant_admin_pwd

for slice in slices:
    
    print 'Cleaning up slice %s' % slice

    if ':' in slice:
        tenant_name = slice # Assume it is a URN
    else:
        tenant_name = 'geni:gpo:gcf+slice+' + slice

    tenant_admin = 'admin-' + tenant_name

    # Figure out the uuid of this tenant
    cmd_string = 'keystone tenant-list' 
    print cmd_string
    output = open_stack_interface._execCommand(cmd_string)
    tenant_uuid = open_stack_interface._getUUIDByName(output, tenant_name)
    if tenant_uuid == None :
        # Tenant does not exist.  Exit!
        print 'Cannot find tenant %s\n' % tenant_name
        sys.exit(1)

    # Figure out the uuid of the tenant admin
    cmd_string = 'keystone user-list'
    print cmd_string
    output = open_stack_interface._execCommand(cmd_string)
    tenant_admin_uuid = open_stack_interface._getUUIDByName(output,
                                                            tenant_admin)
    if tenant_admin_uuid == None :
        # Tenant admin does not exist but tenant does.  Delete the tenant
        # and then exit.
        print 'Cannot find admin user for  %s\n' % tenant_name
        cmd_string = 'keystone tenant-delete %s' % tenant_uuid
        print cmd_string
        open_stack_interface._execCommand(cmd_string)
        sys.exit(1)
                                                            
    # List all VMs owned by this tenant
    cmd_string = 'nova --os-username=%s --os-password=%s --os-tenant-name=%s list' % (tenant_admin, tenant_pwd, tenant_name)
    print cmd_string
    output = open_stack_interface._execCommand(cmd_string)

    # Delete the VMs
    output_lines = output.split('\n')
    for i in range(3, len(output_lines) - 2) :
        columns = output_lines[i].split('|')
        vm_uuid = columns[1]
        cmd_string = 'nova delete %s' % vm_uuid
        print cmd_string
        open_stack_interface._execCommand(cmd_string)

        # Delete the SSH Proxy assoicated with the VM
        cntrlNet = columns[4].split('=')
        net_str_length = len(cntrlNet)
        if net_str_length >= 2 :
            control_nic_ipaddr = cntrlNet[net_str_length - 1].strip()
            manage_ssh_proxy._removeProxy(control_nic_ipaddr)

    # Find all ports of this tenant
    ports_cmd_string = 'quantum port-list -- --tenant_id=%s' % tenant_uuid
    ports_output = open_stack_interface._execCommand(ports_cmd_string)
    port_lines = ports_output.split('\n')
    for i in range(3, len(port_lines)-2):
        port_columns = port_lines[i].split('|')
        port_id = port_columns[1].strip()
        try:
            delete_port_cmd = 'quantum port-delete %s' % port_id
            print delete_port_cmd
            open_stack_interface._execCommand(delete_port_cmd)
        except Exception:
            # Sometimes deleting one port automatically deletes another 
            # so it is no longer there
            # Also, some ports belong to the network:router_interface and
            # can't be deleted from the port API
            pass 

    # Find the networks owned by this tenant and delete them
    cmd_string = 'quantum net-list -- --tenant_id %s' % tenant_uuid
    print cmd_string
    net_list_output = open_stack_interface._execCommand(cmd_string)
    net_list_output_lines = net_list_output.split('\n')
    for i in range(3, len(net_list_output_lines) - 2) :
        columns = net_list_output_lines[i].split('|')
        net_uuid = columns[1]
        cmd_string = 'quantum net-delete %s' % net_uuid
        print cmd_string
        open_stack_interface._execCommand(cmd_string)

    # Delete the security group associated with the tenant
    cmd_string = 'nova --os-username=%s --os-password=%s --os-tenant-name=%s secgroup-delete %s_secgrp ' % (tenant_admin, tenant_pwd, tenant_name, tenant_name)
    print cmd_string
    sec_grp_delete_attempts = 0
    while sec_grp_delete_attempts < 3 :
        try :
            open_stack_interface._execCommand(cmd_string)
            print 'Deleted security group for this tenant'
            break
        except :
            # Failure to delete a security group is usually because one or
            # VMs in this security group are still in the process of being
            # deleted.  Usually waiting for the deletions to complete will
            # allow us to successfully delete the security group
            sec_grp_delete_attempts += 1
            print 'Failed to delete security group.  Waiting 10 seconds to try again...'
            time.sleep(10)

    # Delete the tenant admin account
    cmd_string = 'keystone user-delete %s' % tenant_admin_uuid
    print cmd_string
    open_stack_interface._execCommand(cmd_string)

    # Delete the tenant
    cmd_string = 'keystone tenant-delete %s' % tenant_uuid
    print cmd_string
    open_stack_interface._execCommand(cmd_string)
    
