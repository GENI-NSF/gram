#!/usr/bin/python
# check on open_stack consistency

import open_stack_interface as osi

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
    

if __name__ == "__main__":
    check_openstack_consistency()
