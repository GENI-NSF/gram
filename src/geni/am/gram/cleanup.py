#!/usr/bin/python

import sys

import config
import open_stack_interface

if len(sys.argv) < 2 :
    print 'Usage: cleanup <slicename>...<slicename>'
    sys.exit(2)

# Use port-show to determine if a given port is a network_router port 
# (and thus shouldn't be deleted)
def determine_network_router_interface(port):
    port_show_cmd = "quantum port-show %s" % port
    try:
        port_show_output = open_stack_interface._execCommand(port_show_cmd)
    except Exception:
        # Sometimes the port doesn't exist: 
        # it was deleted by a previous quantum delete command
        return False
#            print "PSO = " + port_show_output
    port_show_output_lines = port_show_output.split('\n')
    port_is_network_router_interface = False
    for k in range(3, len(port_show_output_lines)-2):
        port_show_columns = port_show_output_lines[k].split('|')
        if port_show_columns[1].strip() == 'device_owner' and \
                port_show_columns[2].strip() == 'network:router_interface':
            port_is_network_router_interface = True
            break
    return port_is_network_router_interface

tenant_pwd = config.tenant_admin_pwd

for i in range(1, len(sys.argv)) :
    
    print 'Cleaning up slice %s' % sys.argv[i]

    if ':' in sys.argv[i]:
        tenant_name = sys.argv[i] # Assume it is a URN
    else:
        tenant_name = 'geni:gpo:gcf+slice+' + sys.argv[i]

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


    # Find all ports (we'll be deleting the ones 
    # on the subnet of the network of this tenant
    ports_cmd_string = 'quantum port-list'
    print ports_cmd_string
    ports_output = open_stack_interface._execCommand(ports_cmd_string)
#    print "PORTS = " + ports_output
    ports_output_lines = ports_output.split('\n')

    # Find the networks owned by this tenant
    # And delete corresponding ports (that aren't owned by network:router_interface
    cmd_string = 'quantum net-list -- --tenant_id %s' % tenant_uuid
    print cmd_string
    net_list_output = open_stack_interface._execCommand(cmd_string)
#    print "NETS = " + net_list_output
    net_list_output_lines = net_list_output.split('\n')
    # And delete ports then subnet
    for i in range(3, len(net_list_output_lines) - 2):
        columns = net_list_output_lines[i].split('|')
        subnet = columns[3].strip()
#        print "SN = " + subnet
        for j in range(3, len(ports_output_lines) - 2):
            port_columns = ports_output_lines[j].split('|')
            port = port_columns[1]
            fixed_ips = port_columns[4]
            fixed_ips_pieces = fixed_ips.split('"')
            if len(fixed_ips_pieces) < 3:
                break
            port_sn = fixed_ips_pieces[3].strip()
#            print "PORT = " + port + " FIPS = " + fixed_ips + " SN = " + port_sn
            port_is_network_router_interface = determine_network_router_interface(port)
            if port_sn == subnet and not port_is_network_router_interface:
#                print "MATCH"
                port_delete_cmd = "quantum port-delete %s" % port
                print port_delete_cmd
                try:
                    port_delete_output = open_stack_interface._execCommand(port_delete_cmd)
                except Exception:
                    # Sometimes deleting a port deletes a partner as well, so the list is stale
                    print "Error deleting port: " + port_delete_cmd
                    

    # Delete the networks 
    for i in range(3, len(net_list_output_lines) - 2) :
        columns = net_list_output_lines[i].split('|')
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
    
