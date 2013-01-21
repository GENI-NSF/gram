
import subprocess
import pdb
import re
import time
import tempfile
import os
import time

import resources
import config
import utils
import gen_metadata
from compute_node_interface import compute_node_command, ComputeNodeInterfaceHandler


def init() :
    """
        Perform OpenStack related initialization.  Called once when the
        GRAM AM starts up.
    """
    return
        

def cleanup(signal, frame) :
    """
        Perform OpenStack related cleanup.  Called when the aggregate 
        is shut down.
    """
    # Delete the control network
    if _control_net_uuid != None :
        cmd_string = 'quantum net_delete %s' % _control_net_uuid
        _execCommand(cmd_string)
        

# users is a list of dictionaries [keys=>list_of_ssh_keys, urn=>user_urn]
def provisionResources(geni_slice, users) :
    """
        Allocate network and VM resources for this slice.
    """
    # Create a new tenant for this slice if we don't already have one.  We
    # will not have a tenant_id associated with this slice if this is the
    # first time allocate is called for this slice.
    if geni_slice.getTenantUUID() == None :
        # Create a tenant_name out of the slice_urn.  Slice urn is of the form
        # urn:publicid:IDN+geni:gpo:gcf+slice+sliceName.  Tenant_name is 
        # everything after the IDN+ i.e. geni:gpo:gcf+slice+sliceName.  
        # To get the tenant_name we find the position of the right-most IDN+ 
        # in the slice_urn.  The tenant_name starts 4 characters after 
        # this IDN+ sub-string.
        slice_urn = geni_slice.getSliceURN()
        tenant_name = slice_urn[slice_urn.rfind('IDN+') + 4 : ]
        geni_slice.setTenantName(tenant_name)

        # Create a new tenant and set the tenant UUID in the Slice object
        tenant_uuid = _createTenant(tenant_name)
        geni_slice.setTenantUUID(tenant_uuid)

        # Create a admin user account for this tenant
        admin_user_info = _createTenantAdmin(tenant_name, tenant_uuid)
        if ('admin_name' in admin_user_info) and  \
                ('admin_pwd' in admin_user_info) and \
                ('admin_uuid' in admin_user_info) :
            geni_slice.setTenantAdminInfo(admin_user_info['admin_name'], 
                                          admin_user_info['admin_pwd'],
                                          admin_user_info['admin_uuid'])
        
        ### This section of code is being commented out until we
        ### have namespaces working and can do per slice/tenant routers
        # Create a router for this tenant.  The name of this router is 
        # R-tenant_name.
        # router_name = 'R-%s' % tenant_name
        # geni_slice.setTenantRouterName(router_name)
        # geni_slice.setTenantRouterUUD(_createRouter(tenant_uuid, router_name))
        # config.logger.info('Created tenant router name = %s, uuid = %s' %
        #                    (router_name, geni_slice.getRouterUUID()))

        ### This section of code should be commented out when we have
        ### namespaces working.
        router_name = config.external_router_name
        geni_slice.setTenantRouterName(router_name)
        geni_slice.setTenantRouterUUID(_getRouterUUID(router_name))

        # Create a control network for this tenant if it does not already
        # exist
        if geni_slice.getControlNetInfo() == None :
            # Don't have a control network.  Create one.
            control_net_info = _createControlNetwork(geni_slice)
            if ('control_net_name' in control_net_info) and \
                    ('control_net_uuid' in control_net_info) and \
                    ('control_subnet_uuid' in control_net_info) and \
                    ('control_net_addr' in control_net_info) :
                geni_slice.setControlNetInfo(control_net_info)

    # For each link in the experimenter topology that does not have an
    # associated quantum network/subnet, set up a network and subnet
    for link in geni_slice.getNetworkLinks() :
        if link.getUUID() == None :
            # This network link has not been set up
            uuids = _createNetworkForLink(link)
            link.setNetworkUUID(uuids['network_uuid'])
            link.setSubnetUUID(uuids['subnet_uuid'])
            link.setAllocationState(config.provisioned)

    # For each VM, assign IP addresses to all its interfaces that are
    # connected to a network link
    for vm in geni_slice.getVMs() :
        for nic in vm.getNetworkInterfaces() :
            if nic.getIPAddress() == None :
                # NIC needs an IP, if it is connected to a link
                link = nic.getLink()
                if link == None :
                    # NIC is not connected to a link.  Go to next NIC
                    break
                
                # NIC is connected to a link.  If the link has a subnet
                # address of the form 10.0.x.0/24, this interface gets the
                # ip address 10.0.x.nnn where nnn is the last octet for this vm
                subnet_addr = link.getSubnet()
                subnet_prefix = subnet_addr[0 : subnet_addr.rfind('0/24')]
                nic.setIPAddress(subnet_prefix + vm.getLastOctet())

    # For each VirtualMachine object in the slice, create an OpenStack
    # VM if such a VM has not already been created
    for vm in geni_slice.getVMs() :
        if vm.getUUID() == None :
            vm_uuid = _createVM(vm, users)
            if vm_uuid == None :
                config.logger.error('Failed to crate vm for node %s' %
                                    vm.getName())
            else :
                vm.setUUID(vm_uuid)
                vm.setAllocationState(config.provisioned)
        

def deleteAllResourcesForSlice(geni_slice) :
    """
        Deallocate all network and VM resources held by this slice.
    """
    sliver_stat_list = utils.SliverList()  # Status list to be returned 

    # For each VM in the slice, delete the VM and its associated network ports
    for vm in geni_slice.getVMs() :
        _deleteVM(vm)
        vm.setAllocationState(config.unallocated)
        sliver_stat_list.addSliver(vm)

    # Delete the networks and subnets alocated to the slice. 
    for link in geni_slice.getNetworkLinks() :
        _deleteNetworkLink(link)
        link.setAllocationState(config.unallocated)
        sliver_stat_list.addSliver(link)

    # Delete the control network for the slice.
    _deleteControlNetwork(geni_slice)

    ### Delete tenant router.  This section is empty right now as we don't
    ### do per-tenant routers as yet.

    # Delete the slice (tenant) admin user account
    admin_name, admin_pwd, admin_uuid = geni_slice.getTenantAdminInfo()
    _deleteUserByUUID(admin_uuid)

    # Delete the tenant
    _deleteTenantByUUID(geni_slice.getTenantUUID())

    return sliver_stat_list.getSliverStatusList()
    


######## Module Private Functions.  All OpenStack commands are issued
######## by these functions.

def _createTenant(tenant_name) :
    """
        Create an OpenStack tenant and return the uuid of this new tenant.
    """
    # Create a tenant
    cmd_string = 'keystone tenant-create --name %s' % tenant_name
    output = _execCommand(cmd_string) 

    # Extract the uuid of the tenant from the output and return uuid
    return _getValueByPropertyName(output, 'id')


def _deleteTenantByUUID(tenant_uuid) :
    """
        Delete the tenant with the given uuid.
    """
    cmd_string = 'keystone tenant-delete %s' % tenant_uuid
    _execCommand(cmd_string)


def _createTenantAdmin(tenant_name, tenant_uuid) :
    """
        Create an admin user account for this tenant.
    """
    admin_name = 'admin-' + tenant_name
    cmd_string = 'keystone user-create --name %s --pass %s --enabled true --tenant-id %s' % (admin_name, config.tenant_admin_pwd, tenant_uuid)
    output = _execCommand(cmd_string) 

    # Extract the admin's uuid from the output
    admin_uuid = _getValueByPropertyName(output, 'id')
    if admin_uuid == None :
        # Failed to create admin account
        config.logger.error('keystone user-create failed')
        return {}

    # We now give this new user the role of adminstrator for this tenant
    # First, get a list of roles configured for this installation
    cmd_string = 'keystone role-list'
    output = _execCommand(cmd_string) 
    
    # From the output, extract the UUID for the role 'admin'
    admin_role_uuid = _getUUIDByName(output, 'admin')

    # Now assign this new user the 'admin' role for this tenant
    cmd_string= 'keystone user-role-add --user-id=%s --role-id=%s --tenant-id=%s' % \
        (admin_uuid, admin_role_uuid, tenant_uuid)
    output = _execCommand(cmd_string) 

    # We verify the above command succeded by getting information about
    # this new user and checking it is associated with this tenant
    cmd_string = 'keystone user-get %s' % admin_uuid
    output = _execCommand(cmd_string) 

    # Get the tenantId property from the output
    if _getValueByPropertyName(output, 'tenantId') != tenant_uuid :
        # Failed to associate this user with the tenant
        config.logger.error('keystone user-role-add failed')
        return {}
    
    # Success!  Return the admin username,  password and uuid.
    return {'admin_name':admin_name, 'admin_pwd':config.tenant_admin_pwd, \
                'admin_uuid':admin_uuid }


def _deleteUserByUUID(user_uuid) :
    """
        Delete the user account for the user with the specified uuid.
    """
    cmd_string = 'keystone user-delete %s' % user_uuid
    _execCommand(cmd_string)


def _createRouter(tenant_name, router_name) :
    """
        Create an OpenStack router and return the uuid of this new router.
    """
    cmd_string = 'quantum router-create --tenant-id %s %s' % (tenant_uuid, 
                                                              router_name)
    output = _execCommand(cmd_string) 

    # Extract the uuid of the router from the output and return uuid
    return _getValueByPropertyName(output, 'id')


def _createControlNetwork(slice_object) :
    """
        Create a control network for this tenant (slice).  This network
        is connected to the external router
    """
    tenant_uuid = slice_object.getTenantUUID()

    # Create the control network
    control_net_name = 'cntrlNet-' + slice_object.getTenantName()
    cmd_string = 'quantum net-create --tenant-id %s %s' % (tenant_uuid,
                                                           control_net_name)
    output = _execCommand(cmd_string)
    control_net_uuid = _getValueByPropertyName(output, 'id')
    
    # Create a subnet (L3 network) for the control network
    control_subnet_addr = slice_object.generateControlNetAddress()
    gateway_addr = \
        control_subnet_addr[0 : control_subnet_addr.rfind('0/24')] + '1'
    cmd_string = 'quantum subnet-create --tenant-id %s --gateway %s %s %s' % \
        (tenant_uuid, gateway_addr, control_net_uuid, control_subnet_addr)
    output = _execCommand(cmd_string) 
    control_subnet_uuid = _getValueByPropertyName(output, 'id')

    # Add an interface for this network to the external router
    external_router_uuid = _getRouterUUID(config.external_router_name)
    cmd_string = 'quantum router-interface-add %s %s' %  \
        (config.external_router_name, control_subnet_uuid)
    _execCommand(cmd_string) 

    return {'control_net_name' : control_net_name, \
                'control_net_uuid' : control_net_uuid, \
                'control_subnet_uuid' : control_subnet_uuid, \
                'control_net_addr' : control_subnet_addr}


def _deleteControlNetwork(slice_object) :
    """
        Delete the control network for this slice.
    """
    control_net_uuid = slice_object.getControlNetInfo()['control_net_uuid']
    if control_net_uuid != None :
        cmd_string = 'quantum net-delete %s' % control_net_uuid
        _execCommand(cmd_string)
        

def _createNetworkForLink(link_object) :
    """
        Creates a network (L2) and subnet (L3) for the link.
        Creates an interface on the slice router for this link.

        Returns UUIDs for the network and subnet as a dictionary keyed by
        'network_uuid' and 'subnet_uuid'.  One or both UUIDs will
        be None on failure.
    """
    slice_object = link_object.getSlice()

    # Create a network with the exprimenter specified name for the link
    tenant_uuid = slice_object.getTenantUUID()
    network_name = link_object.getName()
    cmd_string = 'quantum net-create --tenant-id %s %s' % (tenant_uuid,
                                                           network_name)
    output = _execCommand(cmd_string) 
    network_uuid = _getValueByPropertyName(output, 'id')

    # Now create a subnet for this network.
    # First, get a subnet address of the form 10.0.x.0/24
    subnet_addr = slice_object.generateSubnetAddress()
    link_object.setSubnet(subnet_addr)

    # Determine the ip address of the gateway for this subnet.  If the
    # subnet is 10.0.x.0/24, the gateway will be 10.0.x.1
    gateway_addr = subnet_addr[0 : subnet_addr.rfind('0/24')] + '1'

    cmd_string = 'quantum subnet-create --tenant-id %s --gateway %s %s %s' % \
        (tenant_uuid, gateway_addr, network_uuid, subnet_addr)
    output = _execCommand(cmd_string) 
    subnet_uuid = _getValueByPropertyName(output, 'id')

    # Add an interface for this link to the tenant router 
    router_name = slice_object.getTenantRouterName()
    cmd_string = 'quantum router-interface-add %s %s' % (router_name,
                                                         subnet_uuid)
    output = _execCommand(cmd_string) 
    
    # Set operational status
    link_object.setOperationalState(config.ready)

    return {'network_uuid':network_uuid, 'subnet_uuid': subnet_uuid}


def _deleteNetworkLink(link_object) :
    """
       Delete network and subnet associated with this link_object
    """
    net_uuid = link_object.getNetworkUUID()
    cmd_string = 'quantum net-delete %s' % net_uuid
    _execCommand(cmd_string)

# Return dictionary of 'id' => {'mac_address'=>mac_address, , 'fixed_ips'=>fixed_ips}
#  for each port associated ith a given tenant
def _getPortsForTenant(tenant_uuid):
    cmd_string = 'quantum port-list -- --tenant_id=%s' % tenant_uuid
    output = _execCommand(cmd_string)
    output_lines = output.split('\n')
    ports_info = dict()
    for i in range(3, len(output_lines)-2):
        port_info_columns = output_lines[i].split('|');
        port_id = port_info_columns[1].strip()
        port_mac_address = port_info_columns[3].strip()
        port_fixed_ips = port_info_columns[4].strip()
        port_info = {'mac_address' : port_mac_address, 'fixed_ips' : port_fixed_ips}
        ports_info[port_id] = port_info
#    print 'ports for tenant ' + str(tenant_uuid)
#    print str(ports_info)
    return ports_info


# users is a list of dictionaries [keys=>list_of_ssh_keys, urn=>user_urn]
def _createVM(vm_object, users) :
    slice_object = vm_object.getSlice()
    admin_name, admin_pwd, admin_uuid  = slice_object.getTenantAdminInfo()
    tenant_uuid = slice_object.getTenantUUID()
    os_image_id = _getImageUUID(vm_object.getOSImageName())
    vm_flavor_id = _getFlavorID(vm_object.getVMFlavor())
    vm_name = vm_object.getName()

    # Create network ports for this VM.  Each nic gets a network port
    # First create a port for the control network
    control_net_info = slice_object.getControlNetInfo()
    control_net_addr = control_net_info['control_net_addr'] # subnet address
    control_net_prefix = control_net_addr[0 : control_net_addr.rfind('0/24')]
    control_nic_ipaddr = control_net_prefix + vm_object.getLastOctet()
    vm_object.setControlNetAddr(control_nic_ipaddr)
    control_net_uuid = control_net_info['control_net_uuid']
    control_subnet_uuid = control_net_info['control_subnet_uuid']
    cmd_string = 'quantum port-create --tenant-id %s --fixed-ip subnet_id=%s,ip_address=%s %s' %  \
       (tenant_uuid, control_subnet_uuid, control_nic_ipaddr, control_net_uuid)
    output = _execCommand(cmd_string) 
    control_port_uuid = _getValueByPropertyName(output, 'id')

    # Now create ports for the experiment data networks
    for nic in vm_object.getNetworkInterfaces() :
        link_object = nic.getLink()
        net_uuid = link_object.getNetworkUUID()
        nic_ip_addr = nic.getIPAddress()
        if nic_ip_addr != None :
            subnet_uuid = link_object.getSubnetUUID()
            cmd_string = 'quantum port-create --tenant-id %s --fixed-ip subnet_id=%s,ip_address=%s %s' % (tenant_uuid, subnet_uuid, nic_ip_addr, net_uuid)
            output = _execCommand(cmd_string) 
            nic.setUUID(_getValueByPropertyName(output, 'id'))

    # Now grab and set the mac addresses from the port list
    ports_info = _getPortsForTenant(tenant_uuid)
    for nic in vm_object.getNetworkInterfaces() :
        nic_uuid = nic._uuid
#        print "NIC_UUID " + str(nic_uuid) +" LISTED " + str(ports_info.has_key(nic_uuid))
        if ports_info.has_key(nic_uuid):
            mac_address = ports_info[nic_uuid]['mac_address']
            nic.setMACAddress(mac_address)
            
    # Create the VM.  Form the command string in stages.
    cmd_string = 'nova --os-username=%s --os-password=%s --os-tenant-name=%s' \
        % (admin_name, admin_pwd, slice_object.getTenantName())
    cmd_string += (' boot %s --poll --image %s --flavor %s' % (vm_name, os_image_id,
                                                        vm_flavor_id))

    # Add user meta data to create account, pass keys etc.
    # userdata_filename = '/tmp/userdata.txt'
    userdata_file = tempfile.NamedTemporaryFile(delete=False)
    userdata_filename = userdata_file.name
    gen_metadata.configMetadataSvcs(users, userdata_filename)
    cmd_string += (' --user_data %s.gz' % userdata_filename)
    
    # Now add to the cmd_string information about the NICs to be instantiated
    # First add the NIC for the control network
    cmd_string += ' --nic port-id=%s' % control_port_uuid
    
    # Now add the NICs for the experiment data network
    for nic in vm_object.getNetworkInterfaces() :
        port_uuid = nic.getUUID()
        if port_uuid != None :
            cmd_string += (' --nic port-id=%s' % port_uuid)
            
    # Issue the command to create the VM
    output = _execCommand(cmd_string) 

    # Get the UUID of the VM that was created 
    vm_uuid = _getValueByPropertyName(output, 'id')

    # Delete the temp file
    zipped_userdata_filename = userdata_filename + ".gz"
    os.unlink(zipped_userdata_filename)

    # Wait for the vm status to turn to 'active' and then reboot
    ## while True :
    ##     cmd_string = 'nova show %s' % vm_uuid
    ##     output = _execCommand(cmd_string) 
    ##     vm_state = _getValueByPropertyName(output, 'OS-EXT-STS:vm_state')
    ##     config.logger.info('VM state is %s' % vm_state)
    ##     if vm_state == 'active' :
    ##         break
    ##     time.sleep(3)
        

    # Reboot the VM.  This seems to be necessary for the NICs to get IP addrs 
    ## cmd_string = 'nova --os-username=%s --os-password=%s --os-tenant-name=%s' \
    ##     % (admin_name, admin_pwd, slice_object.getTenantName())
    ## cmd_string += (' reboot %s' % vm_name)
    ## _execCommand(cmd_string) 

    # Set the operational state of the VM to configuring
    vm_object.setOperationalState(config.configuring)

    return vm_uuid


def _deleteVM(vm_object) :
    """
        Delete the OpenStack VM that corresponds to this vm_object.
        Delete the network ports associated with the VM
    """
    # Delete ports associatd with the VM
    for nic in vm_object.getNetworkInterfaces() :
        port_uuid = nic.getUUID()
        cmd_string = 'quantum port-delete %s' % port_uuid
        _execCommand(cmd_string)

    # Delete the VM
    vm_uuid = vm_object.getUUID()
    if vm_uuid != None :
        cmd_string = 'nova delete %s' % vm_uuid
        _execCommand(cmd_string)

    
def _getRouterUUID(router_name) :
    """
        Return the UUID of a router given the name of the router.
        We may not need this function when we have per tenant routers
        working.
    """
    cmd_string = 'quantum router-list'
    output = _execCommand(cmd_string) 

    return _getUUIDByName(output, router_name)


def _getUserUUID(user_name) :
    """
        Return the UUID of the specified OpenStrack user.
    """
    cmd_string = 'keystone user-list'
    output = _execCommand(cmd_string) 

    # Extract and return the uuid of the admin user 
    return _getUUIDByName(output, user_name)


def  _getImageUUID(image_name) :
    """
        Given the name of an OS image (e.g. ubuntu-12.04), returns the 
        UUID of the image.  Returns None if the image cannot be found.
    """
    cmd_string = 'nova image-list'
    output = _execCommand(cmd_string) 

    # Extract and return the uuid of the image
    return _getUUIDByName(output, image_name)


def _getFlavorID(flavor_name) :
    """
        Given the name of maching flavor (e.g. m1.small), returns the 
        id of the flavor.  Returns None if the flavor cannot be found.
    """
    cmd_string = 'nova flavor-list'
    output = _execCommand(cmd_string) 

    # Extract and return the uuid of the image
    return _getUUIDByName(output, flavor_name)

    
def _getUUIDByName(output_table, name) :
    """
        Helper function used to extract the uuid of an OpenStack object
        from the output of commands such as router-list, user-list, etc. 
        The output of these commands is in the form of a table.  The first
        column of the table has uuids of the objects listed and the other 
        columns have information on the objects such as name

        This function finds the table row with the specified OpenStack 
        object (name) and returns column 1 of this table row.
    """
    # Split the output table into lines (rows of the table)
    output_lines = output_table.split('\n')

    # Escape any non-alpanumerics in name
    name = re.escape(name)

    # Find the row in the output table that has an entry for object name
    # Column 1 of this row will have the uuid for this object
    for i in range(len(output_lines)) :
        if re.search(r'\b' + name + r'\b', output_lines[i]) :
            # Found the table row for router_name.  Split this row into 
            # individual columns and pick out column 1
            columns = output_lines[i].split('|')
            return columns[1].strip()

    return None   # Failed to find the uuid


def _getValueByPropertyName(output_table, property_name) :
    """
        OpenStack commands that create objects (e.g. tenant-create, 
        net-create, etc.) and commands that show properties of
        objects (net-show, tenant-get, user-get, etc), return a 
        table with two columms.  The first column has property names
        and the second column has the values of the corresponding 
        properties.
        This function finds the row of the table for the specified
        property_name and returns its corresponding value.   For example,
        if the property_name specified is 'id', the function finds the
        table row:
        | id    |   uuid    |
        and returns the value of id (uuid).

        Returns None if a table row cannot be found for the specified 
        property_name.
    """
    # Split the output into lines (rows of the table)
    output_lines = output_table.split('\n')

    # Escape any non-alpanumerics in property_name
    property_name = re.escape(property_name)

    # Look for the row with property_name
    for i in range(len(output_lines)) :
        if re.search(r'\b' + property_name + r'\b', output_lines[i]) :
            # Found the table row with the id.  Split this row into individual
            # columns and pick out column 2
            columns = output_lines[i].split('|')
            return columns[2].strip()

    return None   # Failed to find the uuid

# Get dictionary of hostnames : hostname => list of services
def _listHosts(onlyForService=None):
    hosts = {}
    command_string = 'nova host-list'
    output = _execCommand(command_string)
    output_lines = output.split('\n')
    for i in range(3, len(output_lines)-2):
        line = output_lines[i]
        parts = line.split('|')
        host_name = parts[1].strip()
        service = parts[2].strip()
        if onlyForService and onlyForService != service: continue
        if not hosts.has_key(host_name): hosts[host_name] = []
        hosts[host_name].append(service)
    return hosts

# Get dictionary of all supported flavors (id => description)
def _listFlavors():
    flavors = {}
    command_string = "nova flavor-list"
    output = _execCommand(command_string)
    output_lines = output.split('\n')
    for i in range(3, len(output_lines)-2):
        line = output_lines[i]
        parts = line.split('|')
        id = int(parts[1].strip())
        name = parts[2].strip()
#        print "ID = " + str(id) + " NAME = " + str(name)
        flavors[id]=name
    return flavors

# Find VLAN's associated with MAC addresses and hostnames
# Return dictionary {mac => {'vlan':vlan, 'host':host}}
def _lookup_vlans_for_tenant(tenant_id):
    map = {}
    hosts = _listHosts('compute')
#    print str(hosts)
    ports = _getPortsForTenant(tenant_id)
#    print str(ports)
    for host in hosts.keys():
        port_data = compute_node_interface.compute_node_command(host, ComputeNodeInterfaceHandler.COMMAND_OVS_VSCTL)
        port_map = _read_vlan_port_map(port_data)
        for port in ports.keys():
            mac = ports[port]['mac_address']
            vlan_id = _lookup_vlan_for_port(port, port_map)
            if vlan_id: 
                map[mac] = {'vlan': vlan_id, 'host':host}
    return map

# Find the VLAN tag associated with given port interface
# The ovs-vsctl show command returns interfaces with a qvo prefix
# and has all ports turncated to their first 12 characters, so
# we match accordingly
def _lookup_vlan_for_port(port, port_map):
    vlan_id = None
    port_prefix = port[:11]
    for port in port_map:
        if port.has_key('interface') and port.has_key('tag'):
            tag = port['tag']
            interface = port['interface']
            interface_suffix = interface[3:]
            if (port_prefix == interface_suffix):
                vlan_id = tag
                break
    return vlan_id

# Produce a iist of port / tag / interface from "ovs_vsctl show" command
def _read_vlan_port_map(port_data):
    ports = []
    lines = port_data.split('\n')
    processing_ports = False
    current_port = None
    current_tag = None
    current_interface = None
    for line in lines:
        line = line.strip()
        if line.find('Bridge') >= 0:
            processing_ports = line.find('br-int') >= 0
        if not processing_ports: continue
        if line.find("Port") >= 0:
            if current_port and current_tag and current_interface:
                port_info = {'port':current_port, 'tag':current_tag, \
                                 'interface':current_interface}
                ports.append(port_info)
                current_interface = None
                current_tag = None
                current_port = None
            parts = line.split(' ')
#            print("PORT PARTS = " + str(parts))
            current_port = parts[1]
            parts = current_port.split('"')
#            print("PORT PARTS = " + str(parts))
            if len(parts) > 1:
                current_port = parts[1]
        if line.find("Interface") >= 0:
            parts = line.split(' ')
#            print("INTERFACE PARTS = " + str(parts))
            current_interface = parts[1]
            parts = current_interface.split('"')
#            print("INTERFACE PARTS = " + str(parts))
            if len(parts) > 1:
                current_interface = parts[1]
        if line.find("tag:") >= 0:
            parts = line.split(' ');
            current_tag = int(parts[1])
#            print("TAG PARTS = " + str(parts))
                
#    print str(ports)
    return ports

def _execCommand(cmd_string) :
    config.logger.info('Issuing command %s' % cmd_string)
    command = cmd_string.split()
    return subprocess.check_output(command) 


def updateOperationalStatus(geni_slice) :
    """
        Update the operational status of all VM resources.
    """
    vms = geni_slice.getVMs()
    for i in range(0, len(vms)) :
        vm_object = vms[i]
        vm_uuid = vm_object.getUUID()
        if vm_uuid != None :
            cmd_string = 'nova show %s' % vm_uuid
            output = _execCommand(cmd_string) 
            vm_state = _getValueByPropertyName(output, 'status')
            if vm_state == 'ACTIVE' :
                vm_object.setOperationalState(config.ready)
            elif vm_state == 'ERROR' :
                vm_object.setOperationalState(config.failed)

    links = geni_slice.getNetworkLinks()
    for i in range(0, len(links)) :
        link_object = links[i]
        network_uuid = link_object.getNetworkUUID() 
        if network_uuid != None :
            link_object.setOperationalState(config.ready)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        tenant_uuid = sys.argv[1]
        ports = _getPortsForTenant(tenant_uuid)
        map = _lookup_vlans_for_tenant(tenant_uuid)
        print str(map)
