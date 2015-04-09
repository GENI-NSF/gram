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

from xml.dom.minidom import *
import socket
import re

import config
import constants
import open_stack_interface
from resources import GramImageInfo, Slice, VirtualMachine, NetworkInterface, NetworkLink
import uuid
import utils
import netaddr
import stitching

def parseRequestRspec(agg_urn, geni_slice, rspec, stitching_handler=None) :
    """ This function parses a request rspec and creates the sliver objects for
        the resources requested by this rspec.  The resources are not actually
        created.

        Returns a tuple (error string, sliver list, controller) :
            error string: String describing any error encountered during parsing
                          None if there is no error.
            sliver list: List of slivers created while parsing the rspec
            controller_link_info: {link_name : controller_url} for links
                for which the URL of the OF controller is set
    """
    # Initialize return values
    error_string = None
    error_code = constants.SUCCESS
    sliver_list = []
    controller_link_info = {}
        
    # Parse the xml rspec
    rspec_dom = parseString(rspec)

    # Look for DOM elements tagged 'node'.  These are the VMs requested by the
    # experimenter.
    # For each node in the rspec, extract experimenter specified information
    node_list = rspec_dom.getElementsByTagName('node')
    for node in node_list :
        # Get information about the node from the rspec
        node_attributes = node.attributes


        # Find the name of the node.  We need to make sure we don't already
        # have a node with this name before we do anything else.
        if node_attributes.has_key('client_id') :
            node_name = node_attributes['client_id'].value
            list_of_existing_vms = geni_slice.getVMs()
            for i in range(0, len(list_of_existing_vms)) :
                if node_name == list_of_existing_vms[i].getName() :
                    # Duplicate name.  Fail this allocate
                    error_string = \
                        'Rspec error: VM with name %s already exists' % \
                        node_name
                    error_code = constants.REQUEST_PARSE_FAILED
                    config.logger.error(error_string)
                    return error_string, error_code, sliver_list, None
        else :
            error_string = 'Malformed rspec: Node name not specified' 
            error_code = constants.REQUEST_PARSE_FAILED
            config.logger.error(error_string)
            return error_string, error_code, sliver_list, None

        # If the node is already bound (component_manager_id is set)
        # Ignore the node if it isn't bound to my component_manager_id
        if node_attributes.has_key('component_manager_id'):
            cmi = node_attributes['component_manager_id'].value
            if cmi  != agg_urn:
                print "Ignoring remote node : %s" % cmi
                continue

        # Create a VirtualMachine object for this node and add it to the list
        # of virtual machines that belong to this slice at this aggregate
        vm_object = VirtualMachine(geni_slice)
        vm_object.setName(node_name)
        sliver_list.append(vm_object)

        # Check for component_id
        compute_hosts = GramImageInfo._compute_hosts.keys()
        if node_attributes.has_key('component_id'):
          ci = getHostFromUrn(node_attributes['component_id'].value)
          if ci:
            if ci.lower() not in compute_hosts:
                error_string = "Invalid value for component_id"
                error_code = constants.UNSUPPORTED
                config.logger.error(error_string)
                return error_string, error_code, sliver_list, None
            vm_object.setComponentName(ci)

        # Check for component_name
        if node_attributes.has_key('component_name'):
            cn = node_attributes['component_id'].value
            if cn.lower() not in compute_hosts:
                error_string = "Invalid value for component_name"
                error_code = constants.UNSUPPORTED
                config.logger.error(error_string)
                return error_string, error_code, sliver_list, None
            vm_object.setComponentName(cn)

        # Make sure there isn't an exclusive="true" clause in the node 
        if node_attributes.has_key("exclusive"):
            value = node_attributes["exclusive"].value
            if value.lower() == 'true':
                error_string = "GRAM instance can't allocate exclusive compute resources"
                error_code = constants.UNSUPPORTED
                config.logger.error(error_string)
                return error_string, error_code, sliver_list, None

        if node_attributes.has_key("external_ip"):
            value = node_attributes["external_ip"].value
            if value.lower() == 'true':
                vm_object.setExternalIp('true')
    
        found = node.getElementsByTagName('emulab:routable_control_ip')
        if found:
            vm_object.setExternalIp('true')


        # Get flavor from the sliver_type
        sliver_type_list = node.getElementsByTagName('sliver_type')
        for sliver_type in sliver_type_list:
            if sliver_type.attributes.has_key('name') :
                sliver_type_name = sliver_type.attributes['name'].value
            else :
                sliver_type_name = config.default_VM_flavor
            if open_stack_interface._getFlavorID(sliver_type_name):
                vm_object.setVMFlavor(sliver_type_name)
                config.logger.info("Setting VM to " + \
                                       str(sliver_type_name))
            else:
                error_string = "Undefined sliver_type flavor " + \
                    str(sliver_type_name)
                error_code = constants.UNSUPPORTED
                config.logger.error(error_string)
                return error_string, error_code, sliver_list, None

            # Get disk image by name from node
            disk_image_list = sliver_type.getElementsByTagName('disk_image')
            for disk_image in disk_image_list:
                if disk_image.attributes.has_key('name') :
                    disk_image_name = disk_image.attributes['name'].value
                else :
                    disk_image_name = config.default_OS_image
                if disk_image.attributes.has_key('os'):
                    os_type = disk_image.attributes['os'].value
                else:
                    os_type = config.default_OS_type
                if disk_image.attributes.has_key('version'):
                    os_version = disk_image.attributes['version'].value
                else:
                    os_version = config.default_OS_version
                disk_image_uuid = \
                    open_stack_interface._getImageUUID(disk_image_name)
                if disk_image_uuid :
                    config.logger.info("DISK = " + str(disk_image_name) + \
                                           " " + str(disk_image_uuid))
                    vm_object.setOSImageName(disk_image_name)
                    vm_object.setOSType(os_type)
                    vm_object.setOSVersion(os_version)
                else:
                    error_string = "Unsupported disk image: " + \
                        str(disk_image_name)
                    error_code = constants.UNSUPPORTED
                    config.logger.error(error_string)
                    return error_string, error_code, sliver_list, None

        
        # Get interfaces associated with the node
        interface_list = node.getElementsByTagName('interface')
        for interface in interface_list :
            # Create a NetworkInterface object this interface and associate
            # it with the VirtualMachine object for the node
            interface_object = NetworkInterface(geni_slice, vm_object)
            vm_object.addNetworkInterface(interface_object)
            
            # Get information about this network interface from rspec
            interface_attributes = interface.attributes
            if interface_attributes.has_key('client_id') :
                interface_object.setName(interface_attributes['client_id'].value)
            else :
                error_string = 'Malformed rspec: Interface name not specified'
                error_code = constants.REQUEST_PARSE_FAILED
                config.logger.error(error_string)
                return error_string, error_code, sliver_list, None
            ip_list = interface.getElementsByTagName('ip')
            if len(ip_list) > 1:
                error_string = 'Malformed rspec: Interface can have only one ip'
                error_code = constants.REQUEST_PARSE_FAILED
                config.logger.error(error_string)
                return error_string, error_code, sliver_list, None
            for ip in ip_list:
                if ip.attributes.has_key('address'):
                    interface_object.setIPAddress(ip.attributes['address'].value)
                if ip.attributes.has_key('netmask'):
                    interface_object.setNetmask(ip.attributes['netmask'].value)
                

        # Get the list of services for this node (install and execute services)
        service_list = node.getElementsByTagName('services')
        # First handle all the install items in the list of services requested
        for service in service_list :
            install_list = service.getElementsByTagName('install')
            for install in install_list :
                install_attributes = install.attributes
                if not (install_attributes.has_key('url') and 
                        install_attributes.has_key('install_path')) :
                    error_string = 'Source URL or destination path missing for install element in request rspec'
                    error_code = constants.REQUEST_PARSE_FAILED
                    config.logger.error(error_string)
                    return error_string, error_code, sliver_list, None

                source_url = install_attributes['url'].value
                destination = install_attributes['install_path'].value
                if install_attributes.has_key('file_type') :
                    file_type = install_attributes['file_type'].value
                else :
                    file_type = None
                vm_object.addInstallItem(source_url, destination, file_type)
                info_string = 'Added install %s to %s' % (source_url, destination)
                config.logger.info(info_string)
        
        # Next take care of the execute services requested
        for service in service_list :
            execute_list = service.getElementsByTagName('execute')
            for execute in execute_list :
                execute_attributes = execute.attributes
                if not execute_attributes.has_key('command') :
                    error_string = 'Command missing for execute element in request rspec'
                    error_code = constants.REQUEST_PARSE_FAILED
                    config.logger.error(error_string)
                    return error_string, error_code, sliver_list, None

                exec_command = execute_attributes['command'].value
                if execute_attributes.has_key('shell') :
                    exec_shell = execute_attributes['shell'].value
                else :
                    exec_shell = config.default_execute_shell
                vm_object.addExecuteItem(exec_command, exec_shell)
                info_string = 'Added executable %s of %s' % (exec_command, exec_shell)
                config.logger.info(info_string)


    # Done getting information about nodes in the rspec.  Now get information
    # about links.
    link_list = [link for link in rspec_dom.getElementsByTagName('rspec')[0].childNodes if
                 link.nodeName == 'link']


    for link in link_list :
#        print 'link: ' + link.toxml()
        # Get information about this link from the rspec
        link_attributes = link.attributes

        # Find the name of the link.  We need to make sure we don't already
        # have a link with this name before we do anything else.
        if link_attributes.has_key('client_id') :
            link_name = link_attributes['client_id'].value
            list_of_existing_links = geni_slice.getNetworkLinks()
            for i in range(0, len(list_of_existing_links)) :
                if link_name == list_of_existing_links[i].getName() :
                    # Duplicate name.  Fail this allocate
                    error_string = \
                        'Rspec error: Link with name %s already exists' % \
                        link_name
                    error_code = constants.REQUEST_PARSE_FAILED
                    config.logger.error(error_string)
                    return error_string, error_code, sliver_list, None
        else :
            error_string = 'Malformed rspec: Link name not specified'
            error_code = constants.REQUEST_PARSE_FAILED
            config.logger.error(error_string)
            return error_string, error_code, sliver_list, None

        # Create a NetworkLink object for this link 
        link_object = NetworkLink(geni_slice)
        link_object.setName(link_name)
        sliver_list.append(link_object)

        # Gather OF Controller for this link (if any)
        controllers = link.getElementsByTagName('openflow:controller')
        if len(controllers) > 0:
            controller_node = controllers[0]
            controller_url = controller_node.attributes['url'].value
            controller_link_info[link_name] = controller_url

        # Get the end-points for this link.  Each end_point is a network
        # interface
        end_points = link.getElementsByTagName('interface_ref')
        subnet = None
        for i in range(len(end_points)) :
            end_point_attributes = end_points[i].attributes
            
            # get the name of the interface at this end_point
            if end_point_attributes.has_key('client_id') :
                interface_name = end_point_attributes['client_id'].value

            # Find the NetworkInterface with this interface_name
            interface_object =  \
                geni_slice.getNetworkInterfaceByName(interface_name)
            if interface_object == None :
                print "Ignoring unknown interface : %s " % interface_name
                continue

            # Set the interface to point to this link
            interface_object.setLink(link_object)

            # Associate this end point (NetworkInterface) with this link
            link_object.addEndpoint(interface_object)

            if interface_object.getIPAddress() and interface_object.getNetmask():
                config.logger.info(" Adding interface with ip : " + interface_object.getIPAddress())
                config.logger.info(" Adding interface with nm : " + interface_object.getNetmask())
                subnet = netaddr.IPAddress(interface_object.getIPAddress()).__and__(netaddr.IPAddress(interface_object.getNetmask())) 
                cidr = netaddr.IPNetwork( '%s/%s' %  (subnet,interface_object.getNetmask()))
                if not link_object.getSubnet():
                    link_object.setSubnet(str(cidr))
                    config.logger.info(" Subnet: " + link_object.getSubnet())
                else:
                    if netaddr.IPNetwork(link_object.getSubnet()).network != cidr.network:
                        config.logger.warn(" Link on multiple subnets: " + str(cidr) + " and " + link_object.getSubnet())
                        config.logger.warn(" Using subnet " + link_object.getSubnet())

        # If we've created a link that has no interfaces for this aggregate, remove it from allocation
        if len(link_object.getEndpoints()) == 0:
            sliver_list.remove(link_object)
            geni_slice.removeSliver(link_object)

    if stitching_handler:
        error_string, error_code, request_details =  \
            stitching_handler.parseRequestRSpec(rspec_dom)

    return error_string, error_code, sliver_list, controller_link_info


def generateManifestForSlivers(geni_slice, geni_slivers, recompute, \
                                   allocate, 
                                   aggregate_urn,  \
                                   stitching_handler = None):
    
    err_code = constants.SUCCESS
    err_output = None

    # Clone the request and set the 'type' to 'manifest
    request = geni_slice.getRequestRspec()
    if request == None:
        return None, constants.REQUEST_PARSE_FAILED, "Empty Request RSpec"

    if isinstance(request, basestring): request = parseString(request)
    manifest_doc = request.cloneNode(True)
    config.logger.error("DOC = %s" % manifest_doc.toxml())
    manifest = manifest_doc.getElementsByTagName('rspec')[0]
    manifest.setAttribute('type', 'manifest')

    # Change schema location from request.xsd to manifest.xsd
    schema_location_tag = 'xsi:schemaLocation'
    if manifest.attributes.has_key(schema_location_tag):
        schema_location = manifest.attributes[schema_location_tag].value
        revised_schema_location = \
            schema_location.replace('request.xsd', 'manifest.xsd')
        manifest.setAttribute(schema_location_tag, revised_schema_location)

    root = Document()
    

    # For each sliver, find the corresponding manifest element
    # and copy relevant information
    for sliver in geni_slivers:
        sliver_element  = None
        client_id = sliver.getName()
        sliver_id = sliver.getSliverURN()
        for child in manifest.childNodes:
            if (isinstance(sliver, NetworkLink) and child.nodeName == 'link')\
                    or \
                    (isinstance(sliver, VirtualMachine) and child.nodeName =='node'):
                if child.attributes['client_id'].value == client_id:
                    sliver_element = child
                    break

        if sliver_element:
            
            updateManifestForSliver(sliver, sliver_element, root, \
                                    aggregate_urn)

        if stitching_handler:
            err_output, err_code = \
                stitching_handler.updateManifestForSliver(manifest, sliver,
                                                          allocate)

            if err_code != constants.SUCCESS:
                return None, err_output, err_code

    return cleanXML(manifest, "MANIFEST"), err_output, err_code


def getRequestElementForSliver(sliver):
    full_request_rspec = parseString(sliver.getRequestRspec()).getElementsByTagName('rspec')[0]
    for child in full_request_rspec.childNodes:
        if child.attributes is None or not child.attributes.has_key('client_id'):
            continue
        client_id = child.attributes['client_id'].value;
        if sliver.getName() == client_id:
            return child
    return None


# Update XML element in manifest with information from given sliver
def updateManifestForSliver(sliver_object, sliver_elt, root, \
                                component_manager_id):
    client_id = sliver_object.getName()
    sliver_id = sliver_object.getSliverURN()

    sliver_elt.setAttribute('component_manager_id', component_manager_id)
    sliver_elt.setAttribute('sliver_id', sliver_id)

    if isinstance(sliver_object, NetworkLink):

        sliver_elt.setAttribute('vlantag', str(sliver_object.getVLANTag()))

    elif isinstance(sliver_object, VirtualMachine):

        hostname = sliver_object.getHost()
        if hostname is not None:
            component_id = config.urn_prefix + 'node+' + hostname
            sliver_elt.setAttribute('component_id', component_id)

        # Add addresses to interfaces on VM
        for interface in sliver_object.getNetworkInterfaces():
            interface_id = interface.getName()
            interface_node = None
            for iface_node in sliver_elt.getElementsByTagName('interface'):
                if iface_node.attributes['client_id'].value == interface_id:
                    interface_node = iface_node
                    break
            if interface_node is not None:
                # Set the MAC address
                mac_address = interface.getMACAddress()
                if mac_address is not None and mac_address != '':
                    interface_node.setAttribute('mac_address', mac_address)

                # Set the IP address
                ip_address = interface.getIPAddress()
                ip_netmask = interface.getNetmask()
                if ip_address is not None and ip_address != '':
                    ip_nodes = interface_node.getElementsByTagName('ip')
                    if len(ip_nodes) == 0:
                        ip_node = root.createElement('ip')
                        interface_node.appendChild(ip_node)
                    else:
                        ip_node = ip_nodes[0]
                    
                    ip_node.setAttribute('address', ip_address)
                    if ip_netmask is not None:
                        ip_node.setAttribute('netmask', ip_netmask) 
                    ip_node.setAttribute('type', 'ip')

        # Add sliver type (if not already there)
        sliver_types = sliver_elt.getElementsByTagName('sliver_type')
        if len(sliver_types) == 0:
            sliver_type = root.createElement('sliver_type')
            sliver_elt.appendChild(sliver_type)
        else:
            sliver_type = sliver_types[0]

        # Set VM flavor in sliver type node
        sliver_type.setAttribute('name', sliver_object.getVMFlavor())

        # Add disk image info to sliver type
        disk_image = root.createElement('disk_image')
        disk_image_name = config.image_urn_prefix + \
            sliver_object.getOSImageName()
        disk_image.setAttribute("name", disk_image_name)

        disk_image_os = sliver_object.getOSType()
        disk_image.setAttribute("os", disk_image_os)

        disk_image_version = sliver_object.getOSVersion()
        disk_image.setAttribute("version", disk_image_version)

        sliver_type.appendChild(disk_image)

        # Add the 'host' tag
        hosts = sliver_elt.getElementsByTagName('host')
        if len(hosts) == 0:
            host = root.createElement("host")
            sliver_elt.appendChild(host)
        else:
            host = hosts[0]
                
        host_name = sliver_object.getName()
        host.setAttribute('name', host_name)

        # Add user services if there are any
        users = sliver_object.getAuthorizedUsers()
        if users is not None and len(users) > 0:
            services = root.createElement("services")
            for user in users:
                login = root.createElement("login")
                login.setAttribute("authentication", "ssh-keys")
                my_host_name = \
                    socket.gethostbyaddr(socket.gethostname())[0]
                #login.setAttribute("externally-routable-ip", sliver_object.getExternalIp())
                if sliver_object.getExternalIp():
                    login.setAttribute("hostname", sliver_object.getExternalIp())
                    login.setAttribute("port", "22")
                else:    
                    login.setAttribute("hostname", config.public_ip)
                    login.setAttribute("port", str(sliver_object.getSSHProxyLoginPort()))
                login.setAttribute("username", user)
                services.appendChild(login)
            sliver_elt.appendChild(services)
        

def cleanXML(doc, label):
    xml = doc.toprettyxml(indent = '    ')
#    config.logger.info("%s = %s" % (label, xml))
    clean_xml = ""
    for line in xml.split('\n'):
        if line.strip():
            clean_xml += line + '\n'
    config.logger.info("Clean %s = %s" % (label, clean_xml))
    return clean_xml


# Generate advertisement RSPEC for aggeregate based on 
# flavors and disk images registered with open stack
def generateAdvertisement(am_urn, stitching_handler = None):

    component_manager_id = am_urn
    component_name = "" #str(uuid.uuid4())
    component_id = 'urn:public:geni:gpo:vm+' + component_name
    exclusive = 'false'
    client_id="VM"

    urn_prefix = getURNprefix(am_urn)
    compute_nodes = GramImageInfo._compute_hosts

    flavors = open_stack_interface._listFlavors()
    sliver_type = config.default_VM_flavor
    node_types = ""
    for flavor_name in flavors.values():
        node_type = '<sliver_type name="%s"/>' % flavor_name
        node_types = node_types + node_type + "\n"

    # Constants for linking compute nodes to switch
    switch_cmid = am_urn
    switch_name = "TORswitch"
    switch_cid = config.urn_prefix + "node+" + switch_name
    switch_iface_cid = config.urn_prefix+"interface+" + switch_name + ":internal"

    #images = open_stack_interface._listImages()
    #print "IMAGES = " + str(images)
    images = config.disk_image_metadata
#    print "IMAGES = " + str(images)
    image_types = ""
    for image in images:
        description = ""
        if config.disk_image_metadata.has_key(image):
            metadata = config.disk_image_metadata[image]
            if metadata.has_key('os'): os = metadata['os']
            if metadata.has_key('version'): version = metadata['version']
            #if metadata.has_key('description'): description = metadata['description']
            description = 'standard'
        disk_image = '      <disk_image name="%s" os="%s" version="%s" description="%s" />' % (image, os, version, description)
        image_types = image_types + disk_image + "\n"

    sliver_block = ''
    for flavor_name in flavors.values():
        entry = '    <sliver_type name="%s">' % flavor_name
        sliver_block = sliver_block + entry + '\n'
        sliver_block = sliver_block + image_types
        sliver_block = sliver_block + '    </sliver_type> \n'

    node_block = ''
    stitching_link_block = ""
    for compute_node in compute_nodes.keys():
        component_id_template = urn_prefix + socket.gethostname() + '+%s+' + compute_node
        component_id = component_id_template % 'node'
        component_id_interface = component_id_template % 'interface'
        interface_block ='    <interface component_id="%s:%s" role="%s"/>\n' % (component_id_interface, 'eth2', 'experimental')
        entry = '<node component_name="%s" component_manager_id="%s" component_id="%s" exclusive="%s">' % \
            (compute_node, component_manager_id, component_id, exclusive)
        node_block = node_block + entry + '\n'
        node_block = node_block + sliver_block
        node_block = node_block + interface_block
        node_block = node_block + '</node> \n \n'

        stitching_link_template = '<link component_name="%s" ' + \
            'component_id="%s">\n' +\
            '<interface_ref component_id="%s:eth2"/>\n' + \
            '<interface_ref component_id="%s"/>\n' + \
            '</link>'
        link_name = "link-" + compute_node
        link_id = urn_prefix + "link+" + switch_name + "_" + compute_node
        stitching_link = stitching_link_template % \
            (link_name, link_id, component_id_interface, switch_iface_cid)
        stitching_link_block = stitching_link_block + "\n" + stitching_link

    # Add links from local switch to remote switch for stitched links
    external_refs = ""
    if stitching_handler and 'edge_points' in config.stitching_info:
        for edge_point in config.stitching_info['edge_points']:
            # ***
            remote_link = edge_point['remote_switch']
            local_link = edge_point['local_link']
            remote_parts = remote_link.split('+')
            remote_name = remote_parts[-1]
            local_name = local_link.split("+")[-1]
            link_cn = local_name + "/" + remote_name
            link_cid = urn_prefix + 'link+' + link_cn
            link_cmid = '+'.join(remote_parts[:2]) + "+authority+am"
            link_template = '<link component_name="%s" component_id="%s">\n' +\
                '   <interface_ref component_id="%s"/>\n' +\
                '   <interface_ref component_id="%s"/>\n' +\
                '</link>'
            external_link = link_template % (link_cn, link_cid, local_link, remote_link)
            stitching_link_block = stitching_link_block + "\n" + external_link
            external_ref = '<external_ref component_id="%s" component_manager_id="%s"/>' % (link_cid, link_cmid)
            external_refs = external_refs + "\n" + external_ref

    # Add node for the switch with interface to all the compute nodes
    switch_node_template = \
        '<node component_manager_id="%s" component_name="%s" ' +\
        'component_id="%s" exclusive="True">'
    switch_hw_type = '   <hardware_type name ="switch" />'
    switch_interface_template = \
        '   <interface component_id="%s" role="experimental"/>'
    switch_node =  switch_node_template % \
        (switch_cmid, switch_name, switch_cid)
    switch_node_ifaces = ""
    switch_node_iface = switch_interface_template % switch_iface_cid
    switch_node_ifaces = "\n" + switch_node_iface
    
    # And (if stitching) interfaces to all stitch ports
    if stitching_handler and 'edge_points' in config.stitching_info:
        for edge_point in config.stitching_info['edge_points']:
            local_link = edge_point['local_link']
            stitch_iface = switch_interface_template % local_link
            switch_node_ifaces = switch_node_ifaces + "\n" + stitch_iface
        
    switch_node = switch_node + "\n" + switch_hw_type + \
        switch_node_ifaces + "\n</node>"
    node_block = node_block + "\n" + switch_node


    POA_header = '<rspec_opstate xmlns="http://www.geni.net/resources/rspec/ext/opstate/1" ' + \
                'aggregate_manager_id=' + '"' + am_urn + '" '

  
    POA_block = POA_header + 'start="OPSTATE_GENI_NOT_READY"> \n' + \
                node_types + \
                '<state name="OPSTATE_GENI_NOT_READY"> \n' + \
                   '<action name="geni_start" next="OPSTATE_GENI_READY"> \n' + \
                       '<description>Boot the node</description> \n' + \
                   '</action> \n' + \
                '<description>VMs begin powered down or inactive. They must be explicitly booted before use.</description> \n' + \
                '</state> \n' + \
                '</rspec_opstate> \n \n' + \
                POA_header + 'start="OPSTATE_GENI_READY"> \n' + \
                node_types + \
                '<state name="OPSTATE_GENI_READY"> \n' + \
                   '<action name="geni_restart" next="OPSTATE_GENI_READY"> \n' + \
                       '<description>Reboot the node</description> \n' + \
                   '</action> \n' + \
                   '<action name="geni_stop" next="OPSTATE_GENI_READY"> \n' + \
                       '<description>The state of the VM</description> \n' + \
                   '</action> \n' +   \
                '<description>The VM has been booted and is ready</description> \n' + \
                '</state> \n' + \
                '</rspec_opstate> \n' + \
                POA_header + 'start="any_state"> \n' + \
                '<state name="any"> \n' + \
                   '<action name="create_snapshot" next="" > \n' + \
                       '<description>Create a public image of an existing snapshot</description> \n' + \
                   '</action> \n' + \
                   '<action name="delete_snapshot" next=""> \n' + \
                       '<description>Delete a public image of a snapshot</description> \n' + \
                   '</action> \n' +   \
                '<description>These operations can be run on VMs in a any state.Must \
                 specify vm_name and snapshot_name in optsfile.</description> \n' + \
                '</state> \n' + \
                '</rspec_opstate> \n'

# custome image list
    ci_block = ""
#    u_images = open_stack_interface._listImages().values()
#    if len(u_images) > len(images):
#      ci_block = '<node component_id="" component_manager_id="' + component_manager_id + '" exclusive="false">\n'
#      ci_block += '<sliver_type name="" >\n'
#      for u_image in u_images:
#        if u_image not in images:  
#            ci_block += '<disk_image name="' + u_image + '"  description="custom"/>\n'
#      ci_block += "</sliver_type>\n"
#      ci_block += "</node>\n"       

#    tmpl = '''  <node component_manager_id="%s"
#        component_name="%s"
#        component_id="%s"
#        exclusive="%s">
#  %s <sliver_type name="%s"> 
#  %s </sliver_type>
#  </node>
#  %s
#  %s
#  </rspec>
#  '''

    schema_locs = ["http://www.geni.net/resources/rspec/3",
                   "http://www.geni.net/resources/rspec/3/ad.xsd",
                   "http://hpn.east.isi.edu/rspec/ext/stitch/0.1/",
                   "http://hpn.east.isi.edu/rspec/ext/stitch/0.1/stitch-schema.xsd",
                   "http://www.geni.net/resources/rspec/ext/opstate/1",
                   "http://www.geni.net/resources/rspec/ext/opstate/1/ad.xsd"]
    advert_header = '''<?xml version="1.0" encoding="UTF-8"?> 
         <rspec xmlns="http://www.geni.net/resources/rspec/3" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="%s" type="advertisement">''' % (' '.join(schema_locs))

    stitching_advertisement =""
#    config.logger.error("STITCHING_HANDLER = %s" % stitching_handler)
    if stitching_handler:
        stitching_advertisement_doc = \
            stitching_handler.generateAdvertisement(switch_cid)
        stitching_advertisement = \
            stitching_advertisement_doc.childNodes[0].toprettyxml()

        stitching_nodes = ""
        stitching_node_elts = stitching_advertisement_doc.getElementsByTagName('node');
        for stitching_node_elt in stitching_node_elts:
            node_id = stitching_node_elt.attributes['id'].value
            stitching_node = stitching_advertisement_doc.createElement("node")
            stitching_node.setAttribute('component_name', node_id)
            stitching_node.setAttribute('component_id', component_id)
            stitching_node.setAttribute('component_manager_id', component_manager_id)
            stitching_node.setAttribute("exclusive", exclusive)
            link_elt = stitching_node_elt.getElementsByTagName('link')[0];
            stitching_node_interface_id = link_elt.attributes['id'].value
            stitching_node_interface_elt = stitching_advertisement_doc.createElement('interface')
            stitching_node_interface_elt.setAttribute('component_id', stitching_node_interface_id)
            stitching_node_interface_elt.setAttribute('role', 'experimental')
            stitching_node.appendChild(stitching_node_interface_elt)

            stitching_nodes += stitching_node.toprettyxml()

        stitching_links = ""
        client_id = 0
        for compute_node in compute_nodes.keys():
            component_id = urn_prefix + socket.gethostname() + '+interface+' + compute_node
            compute_interface_ref = "%s:%s" % (component_id, 'eth2')
            for stitching_node in stitching_node_elts:
                link_elt = stitching_node.getElementsByTagName('link')[0]
                switch_interface_ref = link_elt.attributes['id'].value
                link_id = "stitch-compute-link-%d" % client_id
                client_id = client_id+1
                stitching_link = '<link component_id="%s">\n<interface_ref component_id="%s"/>\n<interface_ref component_id="%s"/>\n</link>\n\n' % \
                    (link_id, compute_interface_ref, switch_interface_ref)
                stitching_links += stitching_link

        
#        node_block = node_block + '\n' + stitching_nodes + '\n' + stitching_links;

    # Need to have a node for every compute node
    #   with its eth2 interface
    # PLUS a node for the switch 'force10'
    #   with all the stitchable interfaces
    # Then a link from every eth2 interface to the swtich

    result = advert_header  + '\n' + external_refs + '\n' + \
        node_block + '\n' + \
        stitching_link_block + '\n' + stitching_advertisement + \
        POA_block + ci_block + '</rspec>'

#        (tmpl % (component_manager_id, component_name, \
#                     component_id, exclusive, node_types, \
#                     sliver_type, image_types,  stitching_advertisement, POA_block)) 
    return result

def getURNprefix(am_urn):
        host = socket.gethostname().split('.')[0]
        m = re.search(r'(.*)' + host + '(.*)',am_urn)
        if m:
            return m.group(1)

def getHostFromUrn(urn):
        m = re.search(r'.*\+node\+(.*)',urn)
        if m:
            return m.group(1)


