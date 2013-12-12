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

# check on open_stack consistency

import open_stack_interface as osi
from compute_node_interface import compute_node_command, ComputeNodeInterfaceHandler

def check_openstack_consistency():
    # Get all the tenants
    tenants = {}
    command_string = "keystone tenant-list"
    output = osi._execCommand(command_string)
    output_lines = output.split('\n')
    for i in range(3, len(output_lines)-2):
        line = output_lines[i]
        parts = line.split('|')
        tenant_id = parts[1].strip()
        name = parts[2].strip()
        tenants[tenant_id] = name

    # Get all VM's
    vms = []
    command_string = 'nova list --all-tenants'
    output = osi._execCommand(command_string)
    output_lines = output.split('\n')
    for i in range(3, len(output_lines)-2):
        line = output_lines[i]
        parts = line.split('|')
        vms.append(parts[1].strip())

    # Get all ports
    ports = []
    command_string = 'quantum port-list'
    output = osi._execCommand(command_string)
    output_lines = output.split('\n')
    for i in range(3, len(output_lines)-2):
        line = output_lines[i]
        parts = line.split('|')
        ports.append(parts[1].strip())

    # Get all nets
    nets = []
    command_string = 'quantum net-list'
    output = osi._execCommand(command_string)
    output_lines = output.split('\n')
    for i in range(3, len(output_lines)-2):
        line = output_lines[i]
        parts = line.split('|')
        nets.append(parts[1].strip())

    print "Checking that all NOVA VM's have a valid tenant ID"

    # Check that all VM's belong to a tenant
    for vm in vms:
        command_string = 'nova show %s' % vm
        output = osi._execCommand(command_string)
        output_lines = output.split('\n')
        tenant_name = '***'
        matching_tenant_id = None
        for i in range(3, len(output_lines)-2):
            line = output_lines[i]
            parts = line.split('|')
            if parts[1].strip() == 'tenant_id':
                tenant_id = parts[2].strip()
                if tenants.has_key(tenant_id):
                    tenant_name = tenants[tenant_id]
                    break
        print "VM " + vm + " " + str(tenant_id) + " " + str(tenant_name)


    print 
    print "Checking that all QUANTUM ports have a valid tenant ID"
    for port in ports:
        command_string = 'quantum port-show %s' % port
        output = osi._execCommand(command_string)
        output_lines = output.split('\n')
        tenant_id = ''
        for i in range(3, len(output_lines)-2):
            line = output_lines[i]
            parts = line.split('|')
            if parts[1].strip() == 'tenant_id':
                tenant_id = parts[2].strip()
                tenant_name = '***'
                if tenants.has_key(tenant_id): 
                    tenant_name = tenants[tenant_id]
                break
        print "PORT " + port + " " + tenant_id + " " + str(tenant_name)
    

    print 
    print "Checking that all QUANTUM nets have a valid tenant ID"
    for net in nets:
        command_string = 'quantum net-show %s' % net
        output = osi._execCommand(command_string)
        output_lines = output.split('\n')
        tenant_id = ''
        for i in range(3, len(output_lines)-2):
            line = output_lines[i]
            parts = line.split('|')
            if parts[1].strip() == 'tenant_id':
                tenant_id = parts[2].strip()
                tenant_name = '***'
                if tenants.has_key(tenant_id):
                    tenant_name = tenants[tenant_id]
                break
        print "NET " + port + " " + tenant_id + " " + str(tenant_name)

# Check that all ports defined on br-int switches are
# associated with quantum ports
def check_port_consistency():

    print
    print "Checking that all ports defined on br-int are associated with quantum ports"

    # Get list of all currently defined quantum ports
    port_data = osi._getPortsForTenant(None)
    short_port_names = {}
    for port_name in port_data.keys():
        short_name = port_name[:11]
        short_port_names[short_name] = port_name

#    print short_port_names
#    print port_data

    hosts = osi._listHosts(onlyForService='compute')
    for host in hosts:
        switch_data = compute_node_command(host, ComputeNodeInterfaceHandler.COMMAND_OVS_OFCTL);
        switch_data_lines = switch_data.split('\n')
        for i in range(len(switch_data_lines)):
            line = switch_data_lines[i]
            if line.find('qvo') >= 0:
                line_parts = line.split('(')
                port_name_part = line_parts[1]
                port_name = port_name_part.split(')')[0]
                short_name = port_name[3:]
                print port_name + " " + host + " *** "
    

if __name__ == "__main__":
    check_openstack_consistency()
    check_port_consistency()
