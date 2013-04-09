
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
import manage_ssh_proxy

import compute_node_interface
from compute_node_interface import compute_node_command, \
    ComputeNodeInterfaceHandler


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
        try :
            _execCommand(cmd_string)
        except :
            pass
        

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
        if tenant_uuid == None :
            # Failed to create a tenant.  Cleanup actions before
            # we return:
            #    - nothing to cleanup
            return 'GRAM internal error: OpenStack failed to create a tenant for slice %s' % geni_slice.getSliceURN()
        else :
            geni_slice.setTenantUUID(tenant_uuid)

        # Create a admin user account for this tenant
        admin_user_info = _createTenantAdmin(tenant_name, tenant_uuid)
        if ('admin_name' in admin_user_info) and  \
                ('admin_pwd' in admin_user_info) and \
                ('admin_uuid' in admin_user_info) :
            geni_slice.setTenantAdminInfo(admin_user_info['admin_name'], 
                                          admin_user_info['admin_pwd'],
                                          admin_user_info['admin_uuid'])
        else :
            # Failed to create tenant admin.  Cleanup actions before 
            # we return:
            #    - delete the tenant
            _deleteTenantByUUID(tenant_uuid)
            return 'GRAM internal error: OpenStack failed to create a tenant admin for slice %s' % geni_slice.getSliceURN()

        
        # Create a security group for this tenant
        # NOTE: This tenant specific security group support is necessary 
        # to implement the GRAM SSH proxy
        secgroup_name = \
            _createTenantSecurityGroup(tenant_name,
                                       admin_user_info['admin_name'],
                                       admin_user_info['admin_pwd'])
            
        if (secgroup_name != None) :
            geni_slice.setSecurityGroup(secgroup_name)
        else :
            # Failed to create security group.  Cleanup actions before 
            # we return:
            #    - delete tenant admin
            #    - delete tenant
            _deleteUserByUUID(admin_user_info['admin_uuid'])
            _deleteTenantByUUID(tenant_uuid)
            return 'GRAM internal error: OpenStack failed to create a security group for slice %s' % geni_slice.getSliceURN()
        

        ### This section of code is being commented out until we
        ### have namespaces working and can do per slice/tenant routers
        # Create a router for this tenant.  The name of this router is 
        # R-tenant_name.
        # router_name = 'R-%s' % tenant_name
        # geni_slice.setTenantRouterName(router_name)
        # router_uuid = _createRouter(tenant_uuid, router_name)
        # if router_uuid != None :
        #     geni_slice.setTenantRouterUUID(router_uuid)
        #      config.logger.info('Created tenant router %s with uuid = %s' %
        #                    (router_name, geni_slice.getRouterUUID()))
        # else :
        #     INSERT ERROR HANDLING CODE


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
            if control_net_info != None :
                geni_slice.setControlNetInfo(control_net_info)
            else :
                # Failed to create control net.  Cleanup actions before
                # we return:
                #    - delete tenant admin
                #    - delete tenant
                _deleteUserByUUID(admin_user_info['admin_uuid'])
                _deleteTenantByUUID(tenant_uuid)
                return 'GRAM internal error: Failed to create a control network for slice %s' % geni_slice.getSliceURN()

    # For each link in the experimenter topology that does not have an
    # associated quantum network/subnet, set up a network and subnet
    links_created_this_call = list() 
    for link in geni_slice.getNetworkLinks() :
        if link.getUUID() == None :
            # This network link has not been set up
            uuids = _createNetworkForLink(link)
            if uuids == None :
                # Failed to create this network link.  Cleanup actions before
                # we return:
                #    - delete the network links created so far in this
                #      call to provisionResources
                #    - delete the control network for this slice
                #    - delete tenant admin
                #    - delete tenant
                for i in range(0, len(links_created_this_call)) :
                    _deleteNetworkLink(links_created_this_call)
                _deleteControlNetwork(geni_slice)
                _deleteUserByUUID(admin_user_info['admin_uuid'])
                _deleteTenantByUUID(tenant_uuid)
                return 'GRAM internal error: Failed to create a quantum network for link %s' % link.getName()

            link.setNetworkUUID(uuids['network_uuid'])
            link.setSubnetUUID(uuids['subnet_uuid'])
            link.setAllocationState(config.provisioned)
            links_created_this_call.append(uuids['network_uuid'])

    # Associate the VLANs for the control and data networks
    nets_info = _getNetsForTenant(tenant_uuid)
    if nets_info == None :
        # Failed to get information on networks  Cleanup actions before 
        # we return:
        #    - delete the network links created so far in this
        #      call to provisionResources
        #    - delete the control network for this slice
        #    - delete tenant admin
        #    - delete tenant
        for i in range(0, len(links_created_this_call)) :
            _deleteNetworkLink(links_created_this_call)
        _deleteControlNetwork(geni_slice)
        _deleteUserByUUID(admin_user_info['admin_uuid'])
        _deleteTenantByUUID(tenant_uuid)
        return 'GRAM internal error: Failed to get vlan ids for quantum networks created for slice  %s' % geni_slice.getSliceURN()

    control_net_info = geni_slice.getControlNetInfo()
    for net_uuid in nets_info.keys():
        net_info = nets_info[net_uuid]
        vlan = net_info['vlan']
        if net_uuid == control_net_info['control_net_uuid']:
            config.logger.info("Setting control net vlan to " + str(vlan))
            control_net_info['control_net_vlan'] = vlan
        else:
            for link in geni_slice.getNetworkLinks():
                if link.getNetworkUUID() == net_uuid:
                    name = net_info['name']
                    config.logger.info("Setting data net " + name + " VLAN to " + vlan)
                    link.setVLANTag(vlan)

    # For each VM, assign IP addresses to all its interfaces that are
    # connected to a network link
    total_nic_count = 0
    for vm in geni_slice.getVMs() :
        for nic in vm.getNetworkInterfaces() :
            total_nic_count = total_nic_count + 1
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
    # VM if such a VM has not already been created.
    # We try to put the VMs on different compute nodes.  The algorithm for
    # doing this on a rack with N compute nodes is:
    #    1. Let openstack (nova) pick a location for the 1st VM i.e. we don't
    #       provide any hints for placing this VM.
    #    2. For the next N-1 VMs we tell nova to place the VM to be created 
    #       on a node that is different from any of the previous VMs created.
    #       We do this by sending the _createVM call a list of UUIDs for 
    #       VMs created so far.  The nodes on which these VMs are placed are
    #       the ones of avoid.
    #    3. For the remaining VMs, we don't provide nova with any placements
    #       hints.  We'll let the nova scheduler pick compute nodes for 
    #       these VMs.

    # Find out the number of compute nodes we have
    num_compute_nodes = _getComputeNodeCount()
    config.logger.info('Number of compute nodes = %s' % num_compute_nodes)
    
    # Before we create the VMs, we get a list of usernames that get accounts
    # on the VMs when they are created
    user_names = list() 
    for user in users :
        for key in user.keys() :
            # Found a user, there should only be one of these per key in 'user'
            if key == "urn" :
                # We have a urn for the user.  The username is the part of the
                # urn that follows the last +
                user_names.append(user[key].split('+')[-1])
          
    # Now create the VMs.
    num_vms_created = 0    # number of VMs created in this provision call
    vm_uuids = []  # List of uuids of VMs created in this provision call
    vms_created_this_call = [] # List of VM objects corresponding to VMs 
                               # created during this call to provision
    for vm in geni_slice.getVMs() :
        if vm.getUUID() == None :
            # This VM object does not have an openstack VM associated with it.
            # We need to create one.
            if num_vms_created == 0 or num_vms_created >= num_compute_nodes :
                # We are in Step 1 or Step 3 of the VM placement algorithm
                # described above.  We don't give openstack any hints on
                # where this VM should go
                vm_uuid = _createVM(vm, users, total_nic_count, None)
            else :
                vm_uuid = _createVM(vm, users, total_nic_count, vm_uuids)
            if vm_uuid == None :
                # Failed to create this vm.  Cleanup actions before
                # we return:
                #    - delete all the VMs created in this call to provision
                #    - delete the network links created so far in this
                #      call to provisionResources
                #    - delete the control network for this slice
                #    - delete tenant admin
                #    - delete tenant
                for i in range (0, len(vms_created_this_call)) :
                    _deleteVM(vms_created_this_call[i])
                    for i in range(0, len(links_created_this_call)) :
                        _deleteNetworkLink(links_created_this_call)
                    _deleteControlNetwork(geni_slice)
                    _deleteUserByUUID(admin_user_info['admin_uuid'])
                    _deleteTenantByUUID(tenant_uuid)
                config.logger.error('Failed to create vm for node %s' % \
                                        vm.getName())
                return 'GRAM internal error: Failed to create a VM for node %s' % vm.getName()
            else :
                vm.setUUID(vm_uuid)
                vm.setAllocationState(config.provisioned)
                num_vms_created += 1
                vm_uuids.append(vm_uuid)
                vms_created_this_call.append(vm)
                vm.setAuthorizedUsers(user_names)

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
        _deleteNetworkLink(link.getNetworkUUID())
        link.setAllocationState(config.unallocated)
        sliver_stat_list.addSliver(link)

    # Delete the control network for the slice.
    _deleteControlNetwork(geni_slice)

    ### Delete tenant router.  This section is empty right now as we don't
    ### do per-tenant routers as yet.

    # Get information about the tenant admin
    admin_name, admin_pwd, admin_uuid = geni_slice.getTenantAdminInfo()

    # Delete the security group for this tenant
    if admin_name and admin_pwd and admin_uuid:
        time.sleep(10)
        _deleteTenantSecurityGroup(admin_name, admin_pwd,
                                   geni_slice.getTenantName(),
                                   geni_slice.getSecurityGroup())

        # Delete the slice (tenant) admin user account
        _deleteUserByUUID(admin_uuid)

    # Delete the tenant
    tenant_uuid = geni_slice.getTenantUUID()
    if tenant_uuid:
        if _deleteTenantByUUID(geni_slice.getTenantUUID()) == None :
            # Failed to delete this tenant.  We just log the failure.
            config.logger.error('Failed to delete tenant name = %s, uuid = %s'\
                                    % (geni_slice.getTenantName, 
                                       geni_slice.getTenantUUID()))

    return sliver_stat_list.getSliverStatusList()
    


######## Module Private Functions.  All OpenStack commands are issued
######## by these functions.

def _createTenant(tenant_name) :
    """
        Create an OpenStack tenant and return the uuid of this new tenant.
    """
    # Create a tenant
    cmd_string = 'keystone tenant-create --name %s' % tenant_name
    try :
        output = _execCommand(cmd_string) 
    except :
        return None
    else :
        # Extract the uuid of the tenant from the output and return uuid
        return _getValueByPropertyName(output, 'id')


def _deleteTenantByUUID(tenant_uuid) :
    """
        Delete the tenant with the given uuid.
    """
    cmd_string = 'keystone tenant-delete %s' % tenant_uuid
    try :
        _execCommand(cmd_string)
    except :
        return None          # failure
    else :
        return tenant_uuid   # success
        

def _createTenantAdmin(tenant_name, tenant_uuid) :
    """
        Create an admin user account for this tenant.
    """
    admin_name = 'admin-' + tenant_name
    cmd_string = 'keystone user-create --name %s --pass %s --enabled true --tenant-id %s' % (admin_name, config.tenant_admin_pwd, tenant_uuid)
                                
    try :
        output = _execCommand(cmd_string) 
    except :
        # Failed to create admin account
        config.logger.error('Exception during keystone user-create')
        return {}
    else :
        # Extract the admin's uuid from the output
        admin_uuid = _getValueByPropertyName(output, 'id')
        if admin_uuid == None :
            # Failed to create admin account
            config.logger.error('_createTenantAdmin: Cannot find uuid for admin')
            return {}

    # We now give this new user the role of adminstrator for this tenant
    # First, get a list of roles configured for this installation
    cmd_string = 'keystone role-list'
    try :
        output = _execCommand(cmd_string) 
    except :
        # Failed to get a list of roles.  Undo what we've done until now:
        #      - delete the admin user
        config.logger.error('Failed to get a list of user roles')
        _deleteUserByUUID(admin_uuid)      
        return {}
    else :
        # From the output, extract the UUID for the role 'admin'
        admin_role_uuid = _getUUIDByName(output, 'admin')

    # Now assign this new user the 'admin' role for this tenant
    cmd_string= 'keystone user-role-add --user-id=%s --role-id=%s --tenant-id=%s' % \
        (admin_uuid, admin_role_uuid, tenant_uuid)
    try :
        output = _execCommand(cmd_string) 
    except :
        # Failed to make this user an admin.  Undo what we've done until now:
        #      - delete the admin user
        config.logger.error('Failed to give user an admin role')
        _deleteUserByUUID(admin_uuid)      
        return {}

    # Success!  Return the admin username,  password and uuid.
    return {'admin_name':admin_name, 'admin_pwd':config.tenant_admin_pwd, \
                'admin_uuid':admin_uuid }


def _createTenantSecurityGroup(tenant_name, admin_name, admin_pwd) :
    """
        Create a security group for this tenant.
    """
    secgroup_name = '%s_secgrp' % tenant_name

    cmd_string = 'nova --os-username=%s --os-password=%s --os-tenant-name=%s' \
        % (admin_name, admin_pwd, tenant_name)
    cmd_string += ' secgroup-create %s tenant-security-group' % secgroup_name
    try :
        _execCommand(cmd_string) 
    except :
        # Failed to create security group. Cleanup actions before we return:
        #    - No cleanup needed
        return None
    
    # Add a rule to the tenant sec group enabling SSH traffic
    cmd_string = 'nova --os-username=%s --os-password=%s --os-tenant-name=%s' \
        % (admin_name, admin_pwd, tenant_name)
    cmd_string += ' secgroup-add-rule %s tcp 22 22 0.0.0.0/0 ' % secgroup_name
    try :
        _execCommand(cmd_string)
    except :
        # Failed to add rule.  Cleanup actions before we return
        #    - Delete the security group
        _deleteTenantSecurityGroup(admin_name, admin_pwd, tenant_name,
                                   secgroup_name)
        return None
            
    # Add a rule to the tenant sec group enabling ICMP traffic (ping, etc)
    cmd_string = 'nova --os-username=%s --os-password=%s --os-tenant-name=%s' \
        % (admin_name, admin_pwd, tenant_name)
    cmd_string += ' secgroup-add-rule %s icmp -1 -1 0.0.0.0/0 ' % secgroup_name
    try :
        _execCommand(cmd_string)
    except :
        # Failed to add rule.  Cleanup actions before we return
        #    - Delete the security group
        _deleteTenantSecurityGroup(admin_name, admin_pwd, tenant_name,
                                   secgroup_name)

    return secgroup_name    # Success!


def _deleteTenantSecurityGroup(admin_name, admin_pwd, tenant_name, 
                               secgrp_name) :
    """
        Delete the security group created for this tenant
    """
    cmd_string = 'nova --os-username=%s --os-password=%s --os-tenant-name=%s' \
        % (admin_name, admin_pwd, tenant_name)
    cmd_string += ' secgroup-delete %s' % secgrp_name
    try :
        _execCommand(cmd_string) 
    except :
        # Not much we can do other than log the failure
        config.logger.error('Failed to delete security group for tenant %s' % \
                                tenant_name)


def _deleteUserByUUID(user_uuid) :
    """
        Delete the user account for the user with the specified uuid.
    """
    cmd_string = 'keystone user-delete %s' % user_uuid
    try :
        _execCommand(cmd_string)
    except :
        # Not much we can do other than log the failure
        config.logger.error('Failed to delete user account for uuid %s' % \
                                user_uuid)


def _createRouter(tenant_name, router_name) :
    """
        Create an OpenStack router and return the uuid of this new router.
    """
    cmd_string = 'quantum router-create --tenant-id %s %s' % \
        (tenant_uuid, router_name)

    try :
        output = _execCommand(cmd_string) 
    except :
        # Failed to create router.
        config.logger.error('Failed to create router %s' % router_name)
        return None
    else :
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
    try :
        output = _execCommand(cmd_string)
    except :
        # Failed to create control network.  Cleanup actions:
        #    - None
        return None
    else :
        control_net_uuid = _getValueByPropertyName(output, 'id')
    
    # Create a subnet (L3 network) for the control network
    control_subnet_addr = slice_object.generateControlNetAddress()
    gateway_addr = \
        control_subnet_addr[0 : control_subnet_addr.rfind('0/24')] + '1'
    cmd_string = 'quantum subnet-create --tenant-id %s --gateway %s %s %s' % \
        (tenant_uuid, gateway_addr, control_net_uuid, control_subnet_addr)
    try :
        output = _execCommand(cmd_string) 
    except :
        # Failed to create subnet for control network.  Cleanup actions:
        #    - Delete the network that was created
        _deleteControlNetwork(slice_object)
        return None
    else :
        control_subnet_uuid = _getValueByPropertyName(output, 'id')

    # Add an interface for this network to the external router
    external_router_uuid = _getRouterUUID(config.external_router_name)
    cmd_string = 'quantum router-interface-add %s %s' %  \
        (config.external_router_name, control_subnet_uuid)
    try :
        _execCommand(cmd_string) 
    except :
        # Failed to add interface on the external router.  Cleanup actions:
        #    - Delete the network.  Subnets of the network will be 
        #      deleted automatically
        _deleteControlNetwork(slice_object)
        return None

    # Success!
    return {'control_net_name' : control_net_name, \
                'control_net_uuid' : control_net_uuid, \
                'control_subnet_uuid' : control_subnet_uuid, \
                'control_net_addr' : control_subnet_addr}


def _deleteControlNetwork(slice_object) :
    """
        Delete the control network for this slice.
    """
    control_net_info = slice_object.getControlNetInfo()
    if control_net_info :
        control_net_uuid = control_net_info['control_net_uuid']
        if control_net_uuid:
            cmd_string = 'quantum net-delete %s' % control_net_uuid
            try :
                _execCommand(cmd_string)
            except :
                # Failed to delete network.  Not much we can do about it.
                config.logger.error('Failed to delete control network %s' % \
                                        control_net_info['control_net_name'])
                
        
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
                                                           
    try :
        output = _execCommand(cmd_string) 
    except :
        # Failed to create a network for this link.  Cleanup actions:
        #    - None
        return None
    else :
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
    try :
        output = _execCommand(cmd_string) 
    except :
        # Failed to create a subnet.  Cleanup actions:
        #    - Delete the network that was created
        _deleteNetworkLink(network_uuid)
        return None
    else :
        subnet_uuid = _getValueByPropertyName(output, 'id')

    # Add an interface for this link to the tenant router 
    router_name = slice_object.getTenantRouterName()
    cmd_string = 'quantum router-interface-add %s %s' % (router_name,
                                                         subnet_uuid)
    try :
        _execCommand(cmd_string) 
    except :
        # Failed to create interface.  Cleanup actions:
        #    - Delete the network created.  The subnet will be 
        #      deleted automatically
        _deleteNetworkLink(network_uuid)
        return None
        
    # Set operational status
    link_object.setOperationalState(config.ready)

    return {'network_uuid':network_uuid, 'subnet_uuid': subnet_uuid}


def _deleteNetworkLink(net_uuid) :
    """
       Delete network and subnet associated with specified network
    """
    if net_uuid :
        cmd_string = 'quantum net-delete %s' % net_uuid
        try :
            _execCommand(cmd_string)
        except :
            # Failed to delete network.  Not much we can do.
            config.logger.error('Failed to delete network with uuid %s' % \
                                    net_uuid)


def _getNetsForTenant(tenant_uuid):
    cmd_string = 'quantum net-list -- --tenant_id=%s' % tenant_uuid
    try :
        output = _execCommand(cmd_string)
    except :
        # Command failed.  Return None.
        config.logger.error('Failed to get list of networks for tenant %s' % \
                                tenant_uuid)
        return None

    output_lines = output.split('\n')
    nets_info = dict()
    for i in range(3, len(output_lines)-2):
        line = output_lines[i]
        line_parts = line.split('|')
        net_id = line_parts[1].strip()
        name = line_parts[2].strip()
        subnets = line_parts[3].strip()

        cmd_string = 'quantum net-show %s' % net_id
        try :
            net_output = _execCommand(cmd_string)
        except :
            config.logger.error('Failed to get info on network %s' %  net_id)
            return None
            
        net_output_lines = net_output.split('\n')
        belongs = True
        attributes = {'name' : name}
        for j in range(3, len(net_output_lines)-2):
            net_line = net_output_lines[j]
            net_line_parts = net_line.split('|')
            field = net_line_parts[1].strip()
            value = net_line_parts[2].strip()
            if field == 'name' and value != name:
                belongs = False
            elif field == 'tenant_id' and value != tenant_uuid:
                belongs = False
            elif field == 'provider:segmentation_id':
                attributes['vlan'] = value
        if belongs:
            nets_info[net_id] = attributes
    return nets_info

# Return dictionary of 'id' => {'mac_address'=>mac_address, , 'fixed_ips'=>fixed_ips}
#  for each port associated ith a given tenant
def _getPortsForTenant(tenant_uuid):
    cmd_string = 'quantum port-list -- --tenant_id=%s' % tenant_uuid
    try :
        output = _execCommand(cmd_string)
    except :
        config.logger.error('Failed to get port list for tenant %s' % \
                                tenant_uuid)
        return None

    output_lines = output.split('\n')
    ports_info = dict()
    for i in range(3, len(output_lines)-2):
        port_info_columns = output_lines[i].split('|');
        port_id = port_info_columns[1].strip()
        port_mac_address = port_info_columns[3].strip()
        port_fixed_ips = port_info_columns[4].strip()
        port_info = {'mac_address' : port_mac_address, 'fixed_ips' : port_fixed_ips}
        ports_info[port_id] = port_info

    return ports_info


# users is a list of dictionaries [keys=>list_of_ssh_keys, urn=>user_urn]
def _createVM(vm_object, users, total_nic_count, placement_hint) :
    """
        Create a OpenStack VM 
    """
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
        if not link_object: continue
        net_uuid = link_object.getNetworkUUID()
        nic_ip_addr = nic.getIPAddress()
        if nic_ip_addr != None :
            subnet_uuid = link_object.getSubnetUUID()
            cmd_string = 'quantum port-create --tenant-id %s --fixed-ip subnet_id=%s,ip_address=%s %s' % (tenant_uuid, subnet_uuid, nic_ip_addr, net_uuid)
            output = _execCommand(cmd_string) 
            nic.setUUID(_getValueByPropertyName(output, 'id'))

    # Now grab and set the mac addresses from the port list
    ports_info = _getPortsForTenant(tenant_uuid)
    if ports_info == None :
        config.logger.error('Failed to get MAC addresses for network interfaces for tenant %s' % tenant_uuid)
        # Not doing any rollback.  Do we really want to fail the entire 
        # provision if we can't get mac addresses?
    else :
        for nic in vm_object.getNetworkInterfaces() :
            nic_uuid = nic._uuid
            if ports_info.has_key(nic_uuid):
                mac_address = ports_info[nic_uuid]['mac_address']
                nic.setMACAddress(mac_address)

    # Create the VM.  Form the command string in stages.
    cmd_string = 'nova --os-username=%s --os-password=%s --os-tenant-name=%s' \
        % (admin_name, admin_pwd, slice_object.getTenantName())
    cmd_string += (' boot %s --poll --image %s --flavor %s' % \
                       (vm_name, os_image_id, vm_flavor_id))

    # Add user meta data to create account, pass keys etc.
    # userdata_filename = '/tmp/userdata.txt'
    userdata_file = tempfile.NamedTemporaryFile(delete=False)
    userdata_filename = userdata_file.name
    vm_installs = vm_object.getInstalls()
    vm_executes = vm_object.getExecutes()
    gen_metadata.configMetadataSvcs(users, vm_installs, vm_executes, total_nic_count, control_net_prefix, userdata_filename)
    cmd_string += (' --user_data %s.gz' % userdata_filename)

    # Add security group support
    cmd_string += ' --security_groups %s' % slice_object.getSecurityGroup()
    
    # Now add to the cmd_string information about the NICs to be instantiated
    # First add the NIC for the control network
    cmd_string += ' --nic port-id=%s' % control_port_uuid
    
    # Now add the NICs for the experiment data network
    for nic in vm_object.getNetworkInterfaces() :
        port_uuid = nic.getUUID()
        if port_uuid != None :
            cmd_string += (' --nic port-id=%s' % port_uuid)
            
    # Now add any hints for where these should go.  Specifically, if we
    # need to provide a placement_hint (placement_hint != None), we ask
    # nova to try to avoid co-locating this VM with the VMs specified in 
    # placment_hint.
    if placement_hint != None :
        for i in range (0, len(placement_hint)) :
            cmd_string += (' --hint different_host=%s' % placement_hint[i])

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

    # Set up the SSH proxy for the new VM
    portNumber = manage_ssh_proxy._addNewProxy(control_nic_ipaddr)
    vm_object.setSSHProxyLoginPort(portNumber)
    config.logger.info('SSH Proxy assigned port number %d' % portNumber)

    return vm_uuid


def _deleteVM(vm_object) :
    """
        Delete the OpenStack VM that corresponds to this vm_object.
        Delete the network ports associated with the VM
    """
    # Delete ports associatd with the VM
    for nic in vm_object.getNetworkInterfaces() :
        port_uuid = nic.getUUID()
        if port_uuid:
            cmd_string = 'quantum port-delete %s' % port_uuid
            _execCommand(cmd_string)

    # Delete the VM
    vm_uuid = vm_object.getUUID()
    if vm_uuid != None :
        cmd_string = 'nova delete %s' % vm_uuid
        _execCommand(cmd_string)

        # Delete the SSH Proxy support for the VM
        slice_object = vm_object.getSlice()
        control_net_info = slice_object.getControlNetInfo()
        control_net_addr = control_net_info['control_net_addr'] # subnet address
        control_net_prefix = control_net_addr[0 : control_net_addr.rfind('0/24')]
        control_nic_ipaddr = control_net_prefix + vm_object.getLastOctet()
        manage_ssh_proxy._removeProxy(control_nic_ipaddr)

    
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
    try :
        output = _execCommand(cmd_string) 
    except :
        return None
    else :
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


def _getComputeNodeCount() :
    """
        Returns the number of compute nodes on the rack.
    """
    cmd_string = 'nova hypervisor-list'
    output = _execCommand(cmd_string)

    # The output of the above command is a table of the form
    #    +----+---------------------+
    #    | ID | Hypervisor hostname |
    #    +----+---------------------+
    #    | 3  | compute1            |
    #    | 4  | compute2            |
    #    | .. | ...                 |
    #    | N  | computeN            |
    #    +----+---------------------+
    # The number of compute nodes is therefore the number of lines in
    # the output - 5 (there is an extra newline)
    output_lines = output.split('\n')
    return len(output_lines) - 5

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
        flavors[id]=name
    return flavors


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


def _execCommand(cmd_string) :
    """
       Execute the specified command.  Return the output of the command or
       raise and exception if the command execution fails.
    """
    config.logger.info('Issuing command %s' % cmd_string)
    command = cmd_string.split()
    try :
        return subprocess.check_output(command) 
    except :
        config.logger.error('Error executing command %s' % cmd_string)
        raise


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
            try :
                output = _execCommand(cmd_string) 
            except :
                # Failed to update operational status of this VM.   Set the
                # state to failed
                config.logger.error('Failed to find the status of VM for node %s' % vm_object.getName())
                vm_object.setOperationalState(config.failed)
            else :
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

        hosts = _listHosts('compute')
        print "COMPUTE NODES = " + str(hosts)

        nets = _getNetsForTenant(tenant_uuid)
        print str(nets)
        
        ports = _getPortsForTenant(tenant_uuid)
        map = _lookup_vlans_for_tenant(tenant_uuid)
        print str(map)
