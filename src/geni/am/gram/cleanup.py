#!/usr/bin/python

import sys

import config
import open_stack_interface

if len(sys.argv) < 2 :
    print 'Usage: cleanup <slicename>...<slicename>'
    sys.exit(2)

tenant_pwd = config.tenant_admin_pwd

for i in range(1, len(sys.argv)) :
    
    print 'Cleaning up slice %s' % sys.argv[i]

    if ':' in sys.argv[i]:
        tenant_name = sys.argv[i] # Assume it is a URN
    else:
        tenant_name = 'geni:gpo:gcf+slice+' + slice_namesys.argv[i]

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


    # Find the networks owned by this tenant
    cmd_string = 'quantum net-list -- --tenant_id %s' % tenant_uuid
    print cmd_string
    output = open_stack_interface._execCommand(cmd_string)

    # Delete the networks 
    output_lines = output.split('\n')
    for i in range(3, len(output_lines) - 2) :
        columns = output_lines[i].split('|')
        net_uuid = columns[1]
        cmd_string = 'quantum net-delete %s' % net_uuid
        print cmd_string
        open_stack_interface._execCommand(cmd_string)

    # Delete the tenant admin account
    cmd_string = 'keystone user-delete %s' % tenant_admin_uuid
    print cmd_string
    open_stack_interface._execCommand(cmd_string)

    # Delete the tenant
    cmd_string = 'keystone tenant-delete %s' % tenant_uuid
    print cmd_string
    open_stack_interface._execCommand(cmd_string)
    
