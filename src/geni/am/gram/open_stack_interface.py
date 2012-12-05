
import subprocess
import re

import resources
import config

def assignResources(geni_slice) :
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
        router_name = 'externalRouter'
        geni_slice.setTenantRouterName(router_name)
        geni_slice.setTenantRouterUUID(_getRouterUUID(router_name))


    # For each link in the experimenter topology that does not have an
    # associated quantum network/subnet, set up a network and subnet
    for link in geni_slice.getNetworkLinks() :
        if link.getUUID() == None :
            # This network link has not been set up
            uuids = _createNetworkForLink(link)
            link.setNetworkUUID(uuids['network_uuid'])
            link.setSubnetUUID(uuids['subnet_uuid'])

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
            # Need to create an OpenStack VM for this node
            vm_uuid = _createVM(vm)
            if vm_uuid == None :
                config.logger.error('Failed to crate vm for node %s' %
                                    vm.getName())
            else :
                vm.setUUID(vm_uuid)
        

def deleteAllResourcesForSlice(geni_slice) :
    """
        Deallocate all network and VM resources held by this slice.
    """
    # For each VM in the slice, delete the VM and its associated network ports
    for vm in geni_slice.getVMs() :
        _deleteVM(vm)

    # Delete the networks and subnets alocated to the slice. 
    for link in geni_slice.getNetworkLinks() :
        _deleteNetworkLink(link)

    ### Delete tenant router.  This section is empty right now as we don't
    ### do per-tenant routers as yet.

    # Delete the slice (tenant) admin user account
    admin_name, admin_pwd, admin_uuid = geni_slice.getTenantAdminInfo()
    _deleteUserByUUID(admin_uuid)

    # Delete the tenant
    _deleteTenantByUUID(geni_slice.getTenantUUID())
    


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


def _createNetworkForLink(link_object) :
    """
        Creates a network and subnet for the link.
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
    
    return {'network_uuid':network_uuid, 'subnet_uuid': subnet_uuid}


def _deleteNetworkLink(link_object) :
    """
       Delete network and subnet associated with this link_object
    """
    net_uuid = link_object.getNetworkUUID()
    cmd_string = 'quantum net-delete %s' % net_uuid
    _execCommand(cmd_string)

def _createVM(vm_object) :
    slice_object = vm_object.getSlice()
    admin_name, admin_pwd, admin_uuid  = slice_object.getTenantAdminInfo()
    tenant_uuid = slice_object.getTenantUUID()
    os_image_id = _getImageUUID(vm_object.getOSImageName())
    vm_flavor_id = _getFlavorID(vm_object.getFlavor())
    vm_name = vm_object.getName()

    # Create network ports for this VM.  Each nic gets a network port
    for nic in vm_object.getNetworkInterfaces() :
        link_object = nic.getLink()
        net_uuid = link_object.getNetworkUUID()
        nic_ip_addr = nic.getIPAddress()
        if nic_ip_addr != None :
            subnet_uuid = link_object.getSubnetUUID()
            cmd_string = 'quantum port-create --tenant-id %s --fixed-ip subnet_id=%s,ip_address=%s %s' % (tenant_uuid, subnet_uuid, nic_ip_addr, net_uuid)
            output = _execCommand(cmd_string) 
            nic.setPortUUID(_getValueByPropertyName(output, 'id'))
            
    # Create the VM.  Form the command string in stages.
    cmd_string = 'nova --os-username=%s --os-password=%s --os-tenant-name=%s' \
        % (admin_name, admin_pwd, slice_object.getTenantName())
    cmd_string += (' boot %s --image %s --flavor %s' % (vm_name, os_image_id,
                                                        vm_flavor_id))
    
    # Now add to the cmd_string information about the NICs to be instantiated
    for nic in vm_object.getNetworkInterfaces() :
        port_uuid = nic.getPortUUID()
        if port_uuid != None :
            cmd_string += (' --nic port-id=%s' % port_uuid)
            
    # Issue the command to create the VM
    output = _execCommand(cmd_string) 

    # Return the UUID of the VM that was created 
    return  _getValueByPropertyName(output, 'id')


def _deleteVM(vm_object) :
    """
        Delete the OpenStack VM that corresponds to this vm_object.
        Delete the network ports associated with the VM
    """
    # Delete ports associatd with the VM
    for nic in vm_object.getNetworkInterfaces() :
        port_uuid = nic.getPortUUID()
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
    name = re.escape(name)

    # Look for the row with property_name
    for i in range(len(output_lines)) :
        if re.search(r'\b' + property_name + r'\b', output_lines[i]) :
            # Found the table row with the id.  Split this row into individual
            # columns and pick out column 2
            columns = output_lines[i].split('|')
            return columns[2].strip()

    return None   # Failed to find the uuid


def _execCommand(cmd_string) :
    config.logger.info('Issuing command %s' % cmd_string)
    command = cmd_string.split()
    return subprocess.check_output(command) 
