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

import subprocess
import pdb
import re
import time
import tempfile
import os
import uuid
import time
import sys
import string
import netaddr
import json
import threading

import resources
import config
import constants
import utils
import gen_metadata
import manage_ssh_proxy

from xml.dom.minidom import *

import compute_node_interface
from compute_node_interface import compute_node_command, \
    ComputeNodeInterfaceHandler


def init() :
    """
        Perform OpenStack related initialization.  Called once when the
        GRAM AM starts up.
    """
    # Get the UUID of the GRAM management network
    mgmt_net_name = config.management_network_name 
    cmd_string = 'quantum net-list'
    try :
        output = _execCommand(cmd_string)
    except :
        config.logger.error('GRAM AM failed at init.  Failed to do a quantum net-list')
        sys.exit(1)
        
    mgmt_net_uuid = _getUUIDByName(output, mgmt_net_name)
    if mgmt_net_uuid == None :
        config.logger.error('GRAM AM failed at init.  Failed to find the GRAM management network %s' % mgmt_net_name)
        sys.exit(1)

    resources.GramManagementNetwork.set_mgmt_net_uuid(mgmt_net_uuid)
    config.logger.info('Found GRAM managemnet network %s with uuid %s' % \
                           (mgmt_net_name, mgmt_net_uuid))

    resources.GramImageInfo.get_image_list()
    #print output2

    
def cleanup(signal, frame) :
    """
        Perform OpenStack related cleanup.  Called when the aggregate 
        is shut down.
    """
    # Not sure what, if anything we need to do here.  Currently this 
    # function isn't called by anyone.  
    pass
        

def provisionResources(geni_slice, slivers, users, gram_manager) :
    """
        Allocate network and VM resources for this slice.
           geni_slice is the slice_object of the slice being provisioned
           sliver_objects is the list of slivers to be provisioned
           users is a list of dictionaries [keys=>list_of_ssh_keys,
                                            urn=>user_urn]

        Returns None on success
        Returns an error message string on failure.  Failure to provision 
        any sliver results in the entire provision call being rolled back.
    """
    # Create a new tenant for this slice if we don't already have one.  We
    # will not have a tenant_id associated with this slice if this is the
    # first time allocate is called for this slice.
    #import pdb; pdb.set_trace()
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
            #_deleteTenantByUUID(tenant_uuid)
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
            #_deleteUserByUUID(admin_user_info['admin_uuid'])
            #_deleteTenantByUUID(tenant_uuid)
            return 'GRAM internal error: OpenStack failed to create a security group for slice %s' % geni_slice.getSliceURN()
        

        ### This section of code is being commented out until we
        ### have namespaces working and can do per slice/tenant routers
        # Create a router for this tenant.  The name of this router is 
        # R-tenant_name.
        router_name = 'R-%s' % tenant_name
        geni_slice.setTenantRouterName(router_name)
        router_uuid = _createRouter(tenant_uuid, router_name)
        if router_uuid != None :
            geni_slice.setTenantRouterUUID(router_uuid)
            config.logger.info('Created tenant router %s with uuid = %s' %
                            (router_name, router_uuid))
        else:
            print "Not your lucky day!"
            #INSERT ERROR HANDLING CODE


        ### This section of code should be commented out when we have
        ### namespaces working.
        #router_name = config.external_router_name
        #geni_slice.setTenantRouterName(router_name)
        #geni_slice.setTenantRouterUUID(_getRouterUUID(router_name))
    else :
        # Tenant, tenant admin, tenant_router already exist.  Set variables
        # that are used be code below
        tenant_name = geni_slice.getTenantName()
        tenant_uuid = geni_slice.getTenantUUID()
        admin_name, admin_pwd, admin_uuid = geni_slice.getTenantAdminInfo()
        admin_user_info = { 'admin_name' : admin_name,
                            'admin_pwd' : admin_pwd,
                            'admin_uuid' : admin_uuid }

    # We provision all the links before we provision the VMs
    # Walk through the list of sliver_objects in slivers and create two list:
    # links_to_be_provisioned and vms_to_be_provisioned
    links_to_be_provisioned = list()
    vms_to_be_provisioned = list()
    for sliver in slivers :
        if isinstance(sliver, resources.NetworkLink) :
            # sliver is a link object
            links_to_be_provisioned.append(sliver)
        elif isinstance(sliver, resources.VirtualMachine) :
            # sliver is a vm object
            vms_to_be_provisioned.append(sliver)
    config.logger.info('Provisioning %s links and %s vms' % \
                           (len(links_to_be_provisioned), 
                            len(vms_to_be_provisioned))) 

    subnets_used = []
    for link in links_to_be_provisioned:
        if link.getSubnet() != None:
            subnets_used.append(link.getSubnet)

    used_ips = []
    for vm in vms_to_be_provisioned :
        for nic in vm.getNetworkInterfaces() :
            nic.enable()
            if nic.getIPAddress():
               used_ips.append(netaddr.IPAddress(nic.getIPAddress())) 

        for nic in vm.getNetworkInterfaces() :
            if not nic.getIPAddress():
                link = nic.getLink()
                if link == None :
                   # NIC is not connected to a link.  Go to next NIC
                    break

                subnet = link.getSubnet()
                if not subnet:
                    subnet = geni_slice.generateSubnetAddress()
                    while subnet in subnets_used:
                        subnet = geni_slice.generateSubnetAddress()
                    link.setSubnet(subnet)
                subnet_addr = netaddr.IPNetwork(subnet)
                for i in range(1,len(subnet_addr)):
                    if not subnet_addr[i] in used_ips:
                        nic.setIPAddress(str(subnet_addr[i]))
                        used_ips.append(subnet_addr[i])
                        break
                
    # For each VirtualMachine object in the slice, create an  
            
    # For each link to be provisioned, set up a quantum network and subnet if
    # it does not already have one.  (It will have a quantum network and 
    # subnet if it was provisioned by a previous call to provision.)
    links_created_this_call = list()  # Links created by this call to provision
    for link in links_to_be_provisioned :
        if link.getUUID() == None :
            # This network link has not been set up
            uuids = _createNetworkForLink(link,used_ips)
            if uuids == None :
                # Failed to create this network link.  Cleanup actions before
                # we return:
                #    - delete the network links created so far in this
                #      call to provisionResources
                #    - delete tenant admin
                #    - delete tenant
                #for i in range(0, len(links_created_this_call)) :
                #    _deleteNetworkLink(geni_slice, links_created_this_call)
                #_deleteUserByUUID(admin_user_info['admin_uuid'])
                #_deleteTenantByUUID(tenant_uuid)
                return 'GRAM internal error: Failed to create a quantum network for link %s' % link.getName()

            link.setNetworkUUID(uuids['network_uuid'])
            link.setSubnetUUID(uuids['subnet_uuid'])
            link.setUUID(uuids['network_uuid'])
            link.setAllocationState(constants.provisioned)
            links_created_this_call.append(uuids['network_uuid'])
            link.setAllocationState(constants.provisioned)
            link.setOperationalState(constants.ready)

    # Find the VLANs used by this slice
    nets_info = _getNetsForTenant(tenant_uuid)
    if nets_info == None :
        # Failed to get information on networks  Cleanup actions before 
        # we return:
        #    - delete the network links created so far in this
        #      call to provisionResources
        #    - delete tenant admin
        #    - delete tenant
        #for i in range(0, len(links_created_this_call)) :
        #    _deleteNetworkLink(geni_slice, links_created_this_call)
        #_deleteUserByUUID(admin_user_info['admin_uuid'])
        #_deleteTenantByUUID(tenant_uuid)
        return 'GRAM internal error: Failed to get vlan ids for quantum networks created for slice  %s' % geni_slice.getSliceURN()

    for net_uuid in nets_info.keys():
        net_info = nets_info[net_uuid]
        vlan = net_info['vlan']
#        if net_uuid == control_net_info['control_net_uuid']:
#            config.logger.info("Setting control net vlan to " + str(vlan))
#            control_net_info['control_net_vlan'] = vlan
#        else:
        for link in geni_slice.getNetworkLinks():
            if link.getNetworkUUID() == net_uuid:
                name = net_info['name']
                config.logger.info("Setting data net " + name + " VLAN to " + vlan)
                link.setVLANTag(vlan)

    # For each VM, assign IP addresses to all its interfaces that are
    # connected to a network link
    for vm in vms_to_be_provisioned :
        for nic in vm.getNetworkInterfaces() :
            nic.enable()
            #if nic.getIPAddress() == None :
                # NIC needs an IP, if it is connected to a link
            #    link = nic.getLink()
            #    if link == None :
                    # NIC is not connected to a link.  Go to next NIC
            #        break
                
                # NIC is connected to a link.  We assign an IP address to the
                # NIC only if the link it is connected to has been created
           #     if link.getUUID() == None :
                    # NIC is not connected to a link that not been 
                    # provisioned.  Go to next NIC
           #         break

                # NIC is connected to a link that has been provisioned. Give
                # it an IP address.  If IP addresses are from the 
                # 10.0.x.0/24 subnet, this interface gets the
                # ip address 10.0.x.nnn where nnn is the last octet for this vm
          #      subnet_addr = link.getSubnet()
          #      subnet_prefix = subnet_addr[0 : subnet_addr.rfind('0/24')]
          #      nic.setIPAddress(str(netaddr.IPNetwork(subnet_addr)[vm.getLastOctet()]))

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
    
    # Now create the VMs in a background thread (so we return immediately while they are being created/booted)
    create_vms_thread = threading.Thread(target=_createAllVMs, args=(vms_to_be_provisioned, num_compute_nodes, users, gram_manager, geni_slice))
    create_vms_thread.start()

def _createAllVMs(vms_to_be_provisioned, num_compute_nodes, users, gram_manager, slice_object):
    num_vms_created = 0    # number of VMs created in this provision call
    vm_uuids = []  # List of uuids of VMs created in this provision call

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
          

    for vm in vms_to_be_provisioned  :
        if vm.getUUID() == None :
            # This VM object does not have an openstack VM associated with it.
            # We need to create one.
            if num_vms_created == 0 or num_vms_created >= num_compute_nodes :
                # We are in Step 1 or Step 3 of the VM placement algorithm
                # described above.  We don't give openstack any hints on
                # where this VM should go
                vm_uuid = _createVM(vm, users, None)
            else :
                vm_uuid = _createVM(vm, users, vm_uuids)
            if vm_uuid == None :
                # Failed to create this vm.  Cleanup actions before
                # we return:
                #    - delete all the VMs created in this call to provision
                #    - delete the network links created so far in this
                #      call to provisionResources
                #    - delete tenant admin
                #    - delete tenant
                #for i in range (0, len(vms_created_this_call)) :
                #    _deleteVM(vms_created_this_call[i])
                #    for i in range(0, len(links_created_this_call)) :
                #        _deleteNetworkLink(geni_slice, links_created_this_call)
                #    _deleteUserByUUID(admin_user_info['admin_uuid'])
                #    _deleteTenantByUUID(tenant_uuid)
                #config.logger.error('Failed to create vm for node %s' % \
                #                        vm.getName())
                return 'GRAM internal error: Failed to create a VM for node %s' % vm.getName()
            else :
                vm.setUUID(vm_uuid)
                vm.setAllocationState(constants.provisioned)
                num_vms_created += 1
                vm_uuids.append(vm_uuid)
                vm.setAuthorizedUsers(user_names)
                vm.setAllocationState(constants.provisioned)
                vm.setOperationalState(constants.notready)
#                print "VM = %s" % vm
                # Recompute manifest for VM
                gram_manager.update_sliver_manifest(slice_object, vm)

    gram_manager.persist_state() # Save updated state after the VM's are set up
    config.logger.info("Exiting createAllVMs thread...")

# Delete all ports associated with given slice/tenant
# Allow some failures: there will be some that can't be deleted
# Or are automatically deleted by deleting others
# def _deleteNetworkPorts(geni_slice):
#     tenant_uuid = geni_slice.getTenantUUID();
# 
#     ports_cmd = 'quantum port-list -- --tenant_id=%s' % tenant_uuid
#     ports_output = _execCommand(ports_cmd)
#     config.logger.info('ports output = %s' % ports_output)
#     port_lines = ports_output.split('\n')
#     for i in range(3, len(port_lines)-2):
#         port_columns = port_lines[i].split('|')
#         port_id = port_columns[1].strip()
#         try:
#             delete_port_cmd = 'quantum port-delete %s' % port_id
#             print delete_port_cmd
#             _execCommand(delete_port_cmd)
#         except Exception:
#             # Sometimes deleting one port automatically deletes another
#             # so it is no longer there
#             # Also some ports belong to the network:router_interface
#             # and can't be deleted by port API
#             print "Failed to delete port %s" % port_id
#             pass


def deleteSlivers(geni_slice, slivers) :
    """
        Delete the specified sliver_objects (slivers).  All slivers belong
        to the same slice (geni_slice)

        Returns True if all slivers were successfully deleted.
        Returns False if one or more slivers did not get deleted.
    """
    return_val = True  # Value returned by this method.  Be optimistic!

    # We delete all the VMs before we delete the links.
    # Walk through the list of sliver_objects and create two list:
    # links_to_be_deleted and vms_to_be_deleted
    links_to_be_deleted = list()
    vms_to_be_deleted = list()
    for sliver in slivers :
        if isinstance(sliver, resources.NetworkLink) :
            # sliver is a link object
            links_to_be_deleted.append(sliver)
        elif isinstance(sliver, resources.VirtualMachine) :
            # sliver is a vm object
            vms_to_be_deleted.append(sliver)
    config.logger.info('Deleting %s links and %s vms' % \
                           (len(links_to_be_deleted), 
                            len(vms_to_be_deleted))) 

    # For each VM to be deleted, delete the VM and its associated network ports
    for vm in vms_to_be_deleted  :
        success = _deleteVM(vm)
        if success :
            vm.setAllocationState(constants.unallocated)
            vm.setOperationalState(constants.stopping)
        else :
            return_val = False

    if len(links_to_be_deleted) == 0 and geni_slice.getTenantRouterUUID():
        # Delete the router
        router_uuid = geni_slice.getTenantRouterUUID()
        cmd_string = 'quantum router-delete %s' % router_uuid
        try:
            _execCommand(cmd_string)
            geni_slice.setTenantRouterUUID(None)
        except:
            config.logger.error("Failed to delete router %s" % router_uuid)

    # Delete the networks and subnets associated with the links to be deleted 
    for link in links_to_be_deleted :
        success = _deleteNetworkLink(geni_slice,  link.getNetworkUUID())
        if success :
            link.setAllocationState(constants.unallocated)
            link.setOperationalState(constants.stopping)
        else :
            return_val = False

    ### Delete tenant router.  This section is empty right now as we don't
    ### do per-tenant routers as yet.

    return return_val


def expireSlice(geni_slice) :
    """
        Called when a slice is past its expiration time.
    """
    # Delete all slivers that belong to this slice
    slivers = geni_slice.getSlivers().values()
    deleteSlivers(geni_slice, slivers)

    # Get information about the slice tenant admin
    admin_name, admin_pwd, admin_uuid = geni_slice.getTenantAdminInfo()

    # Delete the security group for this tenant
    if admin_name and admin_pwd and admin_uuid:
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
        geni_slice.setTenantUUID(None) # Indicates tenant info is no longer valid

    return 
    


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
    if len(admin_name) > 63:
        admin_name = str(uuid.uuid4())
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
    if secgrp_name == None:
        return
 
    cmd_string = 'nova --os-username=%s --os-password=%s --os-tenant-name=%s' \
        % (admin_name, admin_pwd, tenant_name)
    cmd_string += ' secgroup-delete %s' % secgrp_name

    # We may need to make multiple attempts to delete a security group.  This
    # often happens when a VM using this security group has not yet been 
    # completely deleted.  We try a few times hoping all VMs using this security
    # group will eventually get deleted.  There is no harm if the security 
    # group does not get deleted.  We just keep accumulating security groups
    # that are no longer in use.
    sec_grp_delete_attempts = 0
    while sec_grp_delete_attempts < 4 :
        try :
            _execCommand(cmd_string)
            # Delete successful.  Break out of loop
            break
        except :
            # Delete failed.  Try again if we haven't exceeded our number
            # of retries.
            sec_grp_delete_attempts += 1
            config.logger.info('Retrying delete of security group %s' % \
                                   secgrp_name)
            time.sleep(15)
    if sec_grp_delete_attempts == 4 :
        config.logger.info('Failed to delete security group %s' % secgrp_name)


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
        (tenant_name, router_name)

    try :
        output = _execCommand(cmd_string) 
    except :
        # Failed to create router.
        config.logger.error('Failed to create router %s' % router_name)
        return None
    else :
        # Extract the uuid of the router from the output and return uuid
        return _getValueByPropertyName(output, 'id')


def _createNetworkForLink(link_object,used_ips=None) :
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
    cmd_string = 'quantum net-create %s --tenant-id %s --provider:network_type vlan --provider:physical_network physnet1 --provider:segmentation_id %s' % (network_name, tenant_uuid, link_object.getVLANTag())
                                                           
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
    config.logger.info(" +++ creating link +++")
    config.logger.info(link_object.getSubnet())
    config.logger.info(link_object.getSubnet())

    if not link_object.getSubnet():
        subnet_addr = slice_object.generateSubnetAddress()
        link_object.setSubnet(subnet_addr)
        config.logger.info("No subnet provided, using: " + subnet_addr)
    else:
        subnet_addr = link_object.getSubnet()
        #subnet_addr = slice_object.generateSubnetAddress()

    #test
    #subnet_addr = '10.0.5.0/24'
    # end test
 
    # Determine the ip address of the gateway for this subnet.  If the
    # subnet is 10.0.x.0/24, the gateway will be 10.0.x.1

    subnet_ip = netaddr.IPNetwork(subnet_addr)
    gateway_addr = str(subnet_ip[-2])

    free = None
    for i in range(1,len(subnet_ip)):
        if subnet_ip[i] not in used_ips:
            free = str(subnet_ip[i])
            break

    if not free:
        config.logger.error("No ip left for dhcp agent on subnet " + str(subnet_ip))


    #start_ip =  free
    start_ip = str(subnet_ip[-4])
    end_ip = str(subnet_ip[-3])


    cmd_string = 'quantum subnet-create --tenant-id %s --gateway %s  --allocation-pool start=%s,end=%s  %s %s' % \
        (tenant_uuid, gateway_addr, start_ip,end_ip,network_uuid, subnet_addr)
    try :
        output = _execCommand(cmd_string) 
    except :
        # Failed to create a subnet.  Cleanup actions:
        #    - Delete the network that was created
        _deleteNetworkLink(slice_object, network_uuid)
        return None
    else :
        subnet_uuid = _getValueByPropertyName(output, 'id')

    # create and delete a port on the subnet to create dhcp at a desired address
    #cmd_string = 'quantum port-create --tenant-id %s --fixed-ip subnet_id=%s,ip_address=%s %s' % (tenant_uuid, subnet_uuid,str(subnet_ip[-4]), network_uuid)
    #output = _execCommand(cmd_string)
    #port_uuid = _getValueByPropertyName(output, 'id')
    #cmd_string = 'quantum port-delete %s' % (port_uuid)
    #output = _execCommand(cmd_string)


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
        _deleteNetworkLink(slice_object, network_uuid)
        return None
        
    # Set operational status
    link_object.setOperationalState(constants.ready)

    return {'network_uuid':network_uuid, 'subnet_uuid': subnet_uuid}


def _deleteNetworkLink(slice_object, net_uuid) :
    """
       Delete network and subnet associated with specified network
    """
    if net_uuid :

        # Delete the router interface before deleting the net/subnet"
        subnet_uuid = None
        for link in slice_object.getNetworkLinks():
            if link.getNetworkUUID() == net_uuid:
                subnet_uuid = link.getSubnetUUID()
        router_name = slice_object.getTenantRouterName()
        cmd_string = 'quantum router-interface-delete %s %s' % (router_name, subnet_uuid)
        try:
            _execCommand(cmd_string)
        except:
            config.logger.error("Failed to delete router interface %s %s" % (router_name, subnet_uuid))

        # Delete the router before deleting the net/subnet
        router_uuid = slice_object.getTenantRouterUUID()
        cmd_string = 'quantum router-delete %s' % router_uuid
        try:
            _execCommand(cmd_string)
        except:
            config.logger.error("Failed to delete router %s" % router_uuid)
        


        cmd_string = 'quantum net-delete %s' % net_uuid
        try :
            _execCommand(cmd_string)
        except :
            # Failed to delete network.  Not much we can do.
            config.logger.error('Failed to delete network with uuid %s' % \
                                    net_uuid)
            return False # Failure
        return True # Success


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
def _getPortsForTenant(tenant_uuid,device_id=None):
    if device_id != None:
        cmd_string = 'quantum port-list -- --tenant_id=%s --device_id=%s' % (tenant_uuid,device_id)
    else:
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
def _createVM(vm_object, users, placement_hint):
    """
        Create a OpenStack VM 
    """
    slice_object = vm_object.getSlice()
    admin_name, admin_pwd, admin_uuid  = slice_object.getTenantAdminInfo()
    tenant_uuid = slice_object.getTenantUUID()
    os_image_id = _getImageUUID(vm_object.getOSImageName())
    vm_flavor_id = _getFlavorID(vm_object.getVMFlavor())
    vm_name = vm_object.getName()

    # Assumption: The management network is a /24 network
    # Meta-data services code makes a similar assumption
    mgmt_net_prefix = \
        config.management_network_cidr[0:config.management_network_cidr.rfind('0/24')]

    # Create ports for the experiment data networks
    vm_net_infs = vm_object.getNetworkInterfaces()
    for nic in vm_net_infs :
        if nic.isEnabled() :
            link_object = nic.getLink()
            net_uuid = link_object.getNetworkUUID()
            nic_ip_addr = nic.getIPAddress()
            subnet_uuid = link_object.getSubnetUUID()
            if nic.getIPAddress():
                cmd_string = 'quantum port-create --tenant-id %s --fixed-ip subnet_id=%s,ip_address=%s %s' % (tenant_uuid, subnet_uuid,nic.getIPAddress(), net_uuid)
            else:
                cmd_string = 'quantum port-create --tenant-id %s --fixed-ip subnet_id=%s %s' % (tenant_uuid, subnet_uuid, net_uuid)
            output = _execCommand(cmd_string) 
            nic.setUUID(_getValueByPropertyName(output, 'id'))

    # Now grab and set the mac addresses from the port list
    ports_info = _getPortsForTenant(tenant_uuid)
    if ports_info == None :
        config.logger.error('Failed to get MAC addresses for network interfaces for tenant %s' % tenant_uuid)
        # Not doing any rollback.  Do we really want to fail the entire 
        # provision if we can't get mac addresses?
    else :
        for nic in vm_net_infs :
            nic_uuid = nic._uuid
            if ports_info.has_key(nic_uuid):
                mac_address = ports_info[nic_uuid]['mac_address']
                nic.setMACAddress(mac_address)

    # Create the VM.  Form the command string in stages.
    cmd_string = 'nova --os-username=%s --os-password=%s --os-tenant-name=%s' \
        % (admin_name, admin_pwd, slice_object.getTenantName())
    cmd_string += (' boot %s --config-drive=true --poll --image %s --flavor %s' % \
                       (vm_name, os_image_id, vm_flavor_id))

    component_name = vm_object.getComponentName()
    if component_name:
        config.logger.info("Creating VM on compute node " + component_name)
        cmd_string += ' --availability-zone nova:' + component_name


    # Add user meta data to create account, pass keys etc.
    # userdata_filename = '/tmp/userdata.txt'
    userdata_file = tempfile.NamedTemporaryFile(delete=False)
    userdata_filename = userdata_file.name
    zipped_userdata_filename = userdata_filename #SD + ".gz"
    vm_installs = vm_object.getInstalls()
    vm_executes = vm_object.getExecutes()
    total_nic_count = len(vm_net_infs) + 1
    metadata_cmd_count = gen_metadata.configMetadataSvcs(slice_object, users,
                                                         vm_installs, 
                                                         vm_executes, 
                                                         total_nic_count, 
                                                         mgmt_net_prefix, 
                                                         userdata_filename)
    if metadata_cmd_count > 0 :
        cmd_string += (' --user_data %s' % zipped_userdata_filename)

    # Add security group support
    cmd_string += ' --security_groups %s' % slice_object.getSecurityGroup()
    
    # Tell nova to create a NIC on the VM that is connected to the GRAM 
    # management network
    cmd_string += ' --nic net-id=%s' % \
        resources.GramManagementNetwork.get_mgmt_net_uuid()

    # Now add the NICs for the experiment data network
    for nic in vm_net_infs :
        if nic.isEnabled() :
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
    try :
        output = _execCommand(cmd_string) 
    except :
        config.logger.error('Failed to create VM %s' % vm_name)
        return None

    # Get the UUID of the VM that was created 
    vm_uuid = _getValueByPropertyName(output, 'id')

    # Delete the temp file
    os.unlink(zipped_userdata_filename)

    # Set the operational state of the VM to configuring
    vm_object.setOperationalState(constants.configuring)

    # Create the floating IPs for the VM
    if vm_object.getExternalIp() == 'true':
      ports_info = _getPortsForTenant(tenant_uuid,vm_uuid)
      if ports_info != None :
        for port in ports_info.keys():
            mgmt_ip = eval(ports_info[port]['fixed_ips'])['ip_address']
            found = string.find(mgmt_ip,mgmt_net_prefix)
            if found != -1:
                fip_cmd = "quantum floatingip-create --tenant-id " + tenant_uuid + " public"
                output = _execCommand(fip_cmd)
                fip_id = _getValueByPropertyName(output,'id')
                fip = _getValueByPropertyName(output,'floating_ip_address')
                vm_object.setExternalIp(fip)
                fip_cmd = "quantum floatingip-associate " +  fip_id + " " + port
                output = _execCommand(fip_cmd)


    # Set up the SSH proxy for the new VM
    # Find the IP address for this VM on the management network.  To do this
    # we do a 'nova show vm_uuid' to list properties of the VM and then
    # look for the property with the name of the management network
    cmd_string = 'nova show %s' % vm_uuid
    try :
        output = _execCommand(cmd_string)
    except :
        config.logger.error('Failed to get properties for vm %s' % vm_uuid)
        return None
    property_name = config.management_network_name + ' network'
    mgmt_nic_ipaddr = _getValueByPropertyName(output, property_name)
    compute_host = _getValueByPropertyName(output, 'OS-EXT-SRV-ATTR:host')
    if mgmt_nic_ipaddr != None :
        portNumber = manage_ssh_proxy._addNewProxy(mgmt_nic_ipaddr)
        vm_object.setSSHProxyLoginPort(portNumber)
        vm_object.setHost(compute_host)
        vm_object.setMgmtNetAddr(mgmt_nic_ipaddr)
        config.logger.info('SSH Proxy assigned port number %d to host %s' % \
                               (portNumber, vm_name))

    return vm_uuid

def _createImage(slivers,options):
    found  = False
    uuid = _getImageUUID(options['snapshot_name'])
    if uuid:
        ret_code =  constants.REQUEST_PARSE_FAILED
        ret_str = "Image with this name already exists. Choose a different name"
        return ret_code,ret_str

    for sliver_object in slivers:
        if not isinstance(sliver_object, resources.VirtualMachine): continue
        if sliver_object.getName() == options['vm_name']:
                found = True
                uuid = sliver_object.getUUID()
                nova_cmd = 'nova image-create %s %s' % (uuid,options['snapshot_name'])
                config.logger.info("Performing %s " % nova_cmd)
                try :
                        _execCommand(nova_cmd)
                        ret_code = constants.SUCCESS
                        ret_str = ""
                except:
                        config.logger.error('Failed to perform operational action %s %s: %s' %
                            (action, sliver_object.getUUID(), nova_cmd))
                        ret_code =  constants.REQUEST_PARSE_FAILED
                        ret_str = "Failed to create snapshot"
    if not found:
        ret_code = constants.REQUEST_PARSE_FAILED
        ret_str =  "VM not found"
    return ret_code,ret_str


def _deleteImage(options):
    if options['snapshot_name']:
        cmd = 'image-delete '
        uuid = _getImageUUID(options['snapshot_name'])
        if not uuid:
            config.logger.error("Image not found")
            return constants.UNKNOWN_SLICE,"Image not found"
    else:
        return constants.REQUEST_PARSE_FAILED,"Image not specified"
    nova_cmd = 'nova %s %s' % (cmd, uuid)
    config.logger.info("Performing %s " % nova_cmd)
    try :
        _execCommand(nova_cmd)
    except:
        config.logger.error('Failed to perform operational action %s: %s' %
                            (action, nova_cmd))
        return constants.REQUEST_PARSE_FAILED,"Failed to delete image"
    return constants.SUCCESS,"a"


# Perform operational action (reboot, suspend, resume) on given VM
# By the time this is called, we've already checked that the VM is in 
# the appropriate state
def _performOperationalAction(vm_object, action):

    ret_val = True
    uuid = vm_object.getUUID()
    if action == 'geni_start':
        cmd = 'resume'
    elif action == 'geni_restart':
        cmd = 'reboot'
    elif action == 'geni_stop':
        cmd = 'suspend'
    else:
        return False

    nova_cmd = 'nova %s %s' % (cmd, uuid)
    config.logger.info("Performing %s " % nova_cmd)
 
    try :
        _execCommand(nova_cmd)
    except:
        config.logger.error('Failed to perform operational action %s %s: %s' %
                            (action, vm_object.getUUID(), nova_cmd))
        ret_val = False
    return ret_val

def _deleteVM(vm_object) :
    """
        Delete the OpenStack VM that corresponds to this vm_object.
        Delete the network ports associated with the VM

        Returns True of VM was successfully deleted.  False otherwise.
    """
    return_val = True

    # Delete ports associatd with the VM
    for nic in vm_object.getNetworkInterfaces() :
        port_uuid = nic.getUUID()
        if port_uuid:
            cmd_string = 'quantum port-delete %s' % port_uuid
            try :
                _execCommand(cmd_string)
            except :
                config.logger.error('Failed to delete port %s for VM %s' % \
                                        (port_uuid, vm_object.getName()))

    # Delete floating IPs
    vm_uuid = vm_object.getUUID()
    fip_ids = _getFloatingIpByVM(vm_uuid)
    for fip_id in fip_ids:
        cmd_string = 'quantum floatingip-delete ' + fip_id
        try :
            _execCommand(cmd_string)
        except :
            config.logger.error('Failed to delete floating ip %s for VN %s' % \
                                        (fip_id,vm_object.getName()))


    # Delete the VM
    vm_uuid = vm_object.getUUID()
    if vm_uuid != None :
        cmd_string = 'nova delete %s' % vm_uuid
        try :
            _execCommand(cmd_string)
        except :
            config.logger.error('Failed to delete VM %s with uuid %s' % \
                                    (vm_object.getName(), vm_uuid))
            return_val = False

        # Delete the SSH Proxy support for the VM
        manage_ssh_proxy._removeProxy(vm_object.getMgmtNetAddr())
    else :
        return_val = False

    return return_val


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
    output = resources.GramImageInfo.get_image_list()
    if not _getUUIDByName(output, image_name):
        resources.GramImageInfo.refresh()

    print output
    #cmd_string = 'nova image-list'
    #try :
    #    output = _execCommand(cmd_string)
        #output2 = resources.GramImageInfo.get_image_list() 
        #print output2
    #except :
    #    return None
    #else :
        # Extract and return the uuid of the image
    return _getUUIDByName(output, image_name)


def _getFlavorID(flavor_name) :
    """
        Given the name of maching flavor (e.g. m1.small), returns the 
        id of the flavor.  Returns None if the flavor cannot be found.
    """
    # cmd_string = 'nova flavor-list'
    # output = _execCommand(cmd_string) 
    output = resources.GramImageInfo.get_flavor_list()
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
    #command_string = "nova flavor-list"
    #output = _execCommand(command_string)
    output = resources.GramImageInfo.get_flavor_list()
    output_lines = output.split('\n')
    for i in range(3, len(output_lines)-2):
        line = output_lines[i]
        parts = line.split('|')
        id = int(parts[1].strip())
        name = parts[2].strip()
        flavors[id]=name
    return flavors

# Get dictionary of all supported images (id => name)
def _listImages():
    images ={}
    command_string = "nova image-list"
    #output = _execCommand(command_string)
    output = resources.GramImageInfo.get_image_list()
    #print output2
    output_lines = output.split('\n')
    for i in range(3, len(output_lines)-2):
        line = output_lines[i]
        parts = line.split('|')
        image_id = parts[1].strip()
        image_name = parts[2].strip()
        images[image_id] = image_name

    return images


# Find VLAN's associated with MAC addresses and hostnames
# Return dictionary {mac => {'vlan':vlan, 'host':host}}
def _lookup_vlans_for_tenant(tenant_id):
    map = {}
    hosts = _listHosts('compute')
    ports = _getPortsForTenant(tenant_id)
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

def _getFloatingIpByVM(vm_uuid):
    """ Helper function to get the floating ip assigned to a specified VM
        It uses Quantum to get the ports associated with the VM, then checks
        if there is any floating IP associated with each port. It returns
        a list of IDs of floating IPs of the VM.
    """

    fip_ids = []
    # Get a list of ports on the VM
    cmd = 'quantum port-list --device_id=' + vm_uuid
    output = _execCommand(cmd)
    output_lines = output.split('\n')
    name = 'subnet'
    for line in output_lines:
        if re.search(name, line) :
            columns = line.split('|')
            port_id = columns[1].strip()
            # for each port get a list of associated floating IPs
            output2 = _execCommand("quantum floatingip-list -- --port_id=" + port_id)
            port = re.escape(port_id)
            output_lines2 = output2.split('\n')
            # Find the row in the output table that has the desired port
            for i in range(len(output_lines2)) :
                if re.search(r'\b' + port + r'\b', output_lines2[i]) :
                    # Found the table row for router_name.  Split this row into 
                    # individual columns and pick out column 1
                    columns = output_lines2[i].split('|')
                    config.logger.info("getting floating ip: " + columns[1].strip())
                    fip_ids.append(columns[1].strip())

    return fip_ids


def _getConfigParam(config_file,param):
    """
       Function to parse the gram config file and return the value of the specified parameter
    """

    data = None
    try:
        f = open(config_file, 'r')
        data = f.read()
        f.close()
    except Exception, e:
        print "Failed to read GRAM config file: " + config_file + str(e)
        #config.logger.info("Failed to read GRAM config file: " + config_file)
        return

    data_json = json.loads(data)

    return data_json[param]




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


# Number of seconds must wait before actually updating sliver status
# Calls to 'nova show' and 'nova console-log' are rate limited
# and give errors if you call them too frequenty
UPDATE_OPERATIONAL_STATUS_RATE_LIMIT = 2
def updateOperationalStatus(geni_slice) :
    """
        Update the operational status of all VM resources.
    """
    vms = geni_slice.getVMs()
    for i in range(0, len(vms)) :
        vm_object = vms[i]
        vm_uuid = vm_object.getUUID()
        last_status_update = vm_object.getLastStatusUpdate()
        now = time.time()
        if last_status_update is not None and \
                (now - last_status_update) < UPDATE_OPERATIONAL_STATUS_RATE_LIMIT:
            config.logger.info("Not updating operational status until %f" % \
                                    last_status_update)
            continue;
        vm_object.setLastStatusUpdate(now)
        if vm_uuid != None :
            # If this is an image for which we can look in log
            # to determine successful completion of boot, use that instead
            # of nova show status
            setting_status_by_boot_complete_msg = \
                _set_status_by_boot_complete_msg(vm_object)
            if setting_status_by_boot_complete_msg: continue

            cmd_string = 'nova show %s' % vm_uuid
            try :
                output = _execCommand(cmd_string) 
            except :
                # Failed to update operational status of this VM.   Set the
                # state to failed
                config.logger.error('Failed to find the status of VM for node %s' % vm_object.getName())
                vm_object.setOperationalState(constants.failed)
            else :
                vm_state = _getValueByPropertyName(output, 'status')
                if vm_state == 'ACTIVE' :
                    vm_object.setOperationalState(constants.ready)
                elif vm_state == 'ERROR' :
                    vm_object.setOperationalState(constants.failed)

    links = geni_slice.getNetworkLinks()
    for i in range(0, len(links)) :
        link_object = links[i]
        network_uuid = link_object.getNetworkUUID() 
        if network_uuid != None :
            link_object.setOperationalState(constants.ready)

# If the VM is booted with an image for which a 'boot_complete_msg' is
# registered in the config.disk_image_metadata, use the console-log
# rather than the nova show to determine the operational status
def _set_status_by_boot_complete_msg(vm_object):
    vm_uuid = vm_object.getUUID()
    image_name = vm_object.getOSImageName()
    if not image_name in config.disk_image_metadata or not \
            'boot_complete_msg' in config.disk_image_metadata[image_name]:
        return False

    cmd_string = 'nova console-log --length 2 %s' % vm_uuid
    try :
        output = _execCommand(cmd_string)
    except Exception, e:
        config.logger.error("Failed to get console log %s" % vm_uuid)
        vm_object.setOperationalState(constants.failed)
    else:
#        config.logger.info("VM IMAGE %s TYPE %s VERSION %s" % \
#                               (image_name, vm_object.getOSType(), 
#                                vm_object.getOSVersion()))
        boot_complete_msg = \
            config.disk_image_metadata[image_name]['boot_complete_msg']
        
        boot_done = output.find(boot_complete_msg) >= 0
        config.logger.info("BOOT DONE MATCH = %s %s %s" % (boot_complete_msg, output, boot_done))
        if boot_done:
            vm_object.setOperationalState(constants.ready)
        else:
            vm_object.setOperationalState(constants.notready)

    return True


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
