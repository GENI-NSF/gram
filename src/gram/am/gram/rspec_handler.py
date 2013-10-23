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

import config
import open_stack_interface
from resources import Slice, VirtualMachine, NetworkInterface, NetworkLink
import uuid
import utils
import netaddr
import stitching_rspecs

def parseRequestRspec(geni_slice, rspec) :
    """ This function parses a request rspec and creates the sliver objects for
        the resources requested by this rspec.  The resources are not actually
        created.

        Returns a tuple (error string, sliver list, controller) :
            error string: String describing any error encountered during parsing
                          None if there is no error.
            sliver list: List of slivers created while parsing the rspec
            controller is the url of the OF controller or None
    """
    # Initialize return values
    error_string = None
    sliver_list = []
    controller = None
        
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
                    config.logger.error(error_string)
                    return error_string, sliver_list, None
        else :
            error_string = 'Malformed rspec: Node name not specified' 
            config.logger.error(error_string)
            return error_string, sliver_list, None

        # Create a VirtualMachine object for this node and add it to the list
        # of virtual machines that belong to this slice
        vm_object = VirtualMachine(geni_slice)
        vm_object.setName(node_name)
        sliver_list.append(vm_object)

        # Make sure there isn't an exclusive="true" clause in the node 
        if node_attributes.has_key("exclusive"):
            value = node_attributes["exclusive"].value
            if value.lower() == 'true':
                error_string = "GRAM instance can't allocate exclusive compute resources"
                config.logger.error(error_string)
                return error_string, sliver_list, None

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
                config.logger.error(error_string)
                return error_string, sliver_list, None

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
                    config.logger.error(error_string)
                    return error_string, sliver_list, None

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
                config.logger.error(error_string)
                return error_string, sliver_list, None
            ip_list = interface.getElementsByTagName('ip')
            if len(ip_list) > 1:
                error_string = 'Malformed rspec: Interface can have only one ip'
                config.logger.error(error_string)
                return error_string, sliver_list, None
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
                    config.logger.error(error_string)
                    return error_string, sliver_list, None

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
                    config.logger.error(error_string)
                    return error_string, sliver_list, None

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
    link_list = rspec_dom.getElementsByTagName('link')
    for link in link_list :
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
                    config.logger.error(error_string)
                    return error_string, sliver_list, None
        else :
            error_string = 'Malformed rspec: Link name not specified'
            config.logger.error(error_string)
            return error_string, sliver_list, None

        # Create a NetworkLink object for this link 
        link_object = NetworkLink(geni_slice)
        link_object.setName(link_name)
        sliver_list.append(link_object)

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
                error_string = 'Malformed rspec: Unknown interface_ref %s specified for link %s' % (interface_name, link_object.getName())
                config.logger.error(error_string)
                return error_string, sliver_list, None

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

    controllers = rspec_dom.getElementsByTagName('openflow:controller')
    if len(controllers) > 0:
        controller_node = controllers[0]
        controller = controller_node.attributes['url'].value

    stitching_rspec_handler = stitching_rspecs.Stitching()
    stitching_rspec_handler.parseRequestRSpec(rspec_dom)

    return error_string, sliver_list, controller


def generateManifestForSlivers(geni_slice, geni_slivers, recompute):
    req_rspec = geni_slice.getRequestRspec()
    request = parseString(req_rspec).childNodes[0]

    root = Document()
    manifest = root.createElement("rspec")
    manifest.setAttribute('type', 'manifest')
    root.appendChild(manifest)

    namespace = request.attributes['xmlns'].value
    manifest.setAttribute("xmlns", namespace)
    xml_schema_instance = request.attributes['xmlns:xsi'].value
    manifest.setAttribute("xmlns:xsi", xml_schema_instance)
    xsi_schema_location = request.attributes['xsi:schemaLocation'].value
    xsi_schema_location = xsi_schema_location.replace('request.xsd', 
                                                      'manifest.xsd')
    manifest.setAttribute("xsi:schemaLocation", xsi_schema_location)

    for sliver in geni_slivers:
        sliver_request_element = getRequestElementForSliver(sliver)
        sliver_manifest = None
        sliver_manifest_raw = sliver.getManifestRspec()
        if sliver_manifest_raw is not None: 
            sliver_manifest = parseString(sliver_manifest_raw).childNodes[0]
        if recompute:
            sliver_manifest = \
                generateManifestForSliver(geni_slice, sliver, \
                                              root, sliver_request_element)
            sliver.setManifestRspec(sliver_manifest.toxml())
        if sliver_manifest is not None:
            manifest.appendChild(sliver_manifest)

    stitching_rspec_handler = stitching_rspecs.Stitching()
    stitching_manifest = stitching_rspec_handler.generateManifest(req_rspec)
    if stitching_manifest:
        manifest.appendChild(stitching_manifest)

    return cleanXML(root, "Manifest")

def getRequestElementForSliver(sliver):
    full_request_rspec = parseString(sliver.getRequestRspec()).childNodes[0]
    for child in full_request_rspec.childNodes:
        if child.attributes is None or not child.attributes.has_key('client_id'):
            continue
        client_id = child.attributes['client_id'].value;
        if sliver.getName() == client_id:
            return child
    return None

# def getSliverForRequest(request, slivers):
#     client_id = request.attributes['client_id'].value
#     found = None
#     for sliver in slivers:
#         if sliver.getName() == client_id:
#             found = sliver
#             break
#     return found

# def getSliverRequest(sliver, request):
#     sliver_name = sliver.getName()
#     sliver_request = None
#     for child in request.childNodes:
#         if child.attributes is not None and \
#                 child.attributes.has_key('client_id') and \
#                 child.attributes['client_id'].value == sliver_name:
#             sliver_request = child
#             break
#     return sliver_request

def generateManifestForSliver(geni_slice, geni_sliver, root, request):
    node_name = "node"
    if geni_sliver.__class__ == NetworkLink: node_name = "link"
    node = root.createElement(node_name)

    if geni_sliver.__class__ == NetworkInterface:
        return None

    client_id = geni_sliver.getName()
    node.setAttribute("client_id", client_id)
    sliver_id = geni_sliver.getSliverURN()
    node.setAttribute("sliver_id", sliver_id)
    if geni_sliver.__class__ == NetworkLink:

        for interface in geni_sliver.getEndpoints():
            interface_ref = root.createElement('interface_ref')
            client_id = interface.getName()
            interface_ref.setAttribute('client_id', client_id)
            node.appendChild(interface_ref)

        property_nodes = request.getElementsByTagName('property')
        for property_node in property_nodes:
            node.appendChild(property_node)

        link_type_nodes = request.getElementsByTagName('link_type')
        for link_type_node in link_type_nodes:
            node.appendChild(link_type_node)


    elif geni_sliver.__class__ == VirtualMachine:
        hostname = geni_sliver.getHost()
        if hostname is not None:
            component_id = config.urn_prefix + "node+" + hostname
            node.setAttribute("component_id", component_id)

        component_manager_id = config.urn_prefix + "authority+cm"
        node.setAttribute("component_manager_id", component_manager_id)

        node.setAttribute('exclusive', 'false')

        for interface in geni_sliver.getNetworkInterfaces():
            interface_node = root.createElement("interface")
            interface_client_id = interface.getName()
            # Need to add the mac_address if there is one
            mac_address = interface.getMACAddress()
            if mac_address is not None:
                interface_node.setAttribute("mac_address", mac_address)
            interface_node.setAttribute("client_id", interface_client_id)
            interface_node.setAttribute("sliver_id", interface.getSliverURN())
            # Need to add IP_address if there is one
            ip_address = interface.getIPAddress()
            if ip_address is not None:
                ip_node = root.createElement("ip")
                ip_node.setAttribute("address", ip_address)
                ip_node.setAttribute("type", "ip")
                interface_node.appendChild(ip_node)
            node.appendChild(interface_node)

        sliver_type = root.createElement("sliver_type")
        sliver_type_name = geni_sliver.getVMFlavor()
        sliver_type.setAttribute("name", sliver_type_name)

        disk_image = root.createElement("disk_image")

        disk_image_name = config.image_urn_prefix + \
            geni_sliver.getOSImageName()
        disk_image.setAttribute("name", disk_image_name)


        disk_image_os = geni_sliver.getOSType()
        disk_image.setAttribute("os", disk_image_os)

        disk_image_version = geni_sliver.getOSVersion()
        disk_image.setAttribute("version", disk_image_version)

        sliver_type.appendChild(disk_image)
        node.appendChild(sliver_type)

        # Need to add the services, if there are any
        users = geni_sliver.getAuthorizedUsers()
        if users is not None and len(users) > 0:
            services = root.createElement("services")
            for user in users:
                login = root.createElement("login")
                login.setAttribute("authentication", "ssh-keys")
                my_host_name = \
                    socket.gethostbyaddr(socket.gethostname())[0]
                login.setAttribute("externally-routable-ip", geni_sliver.getExternalIp())
                login.setAttribute("username", user)
                services.appendChild(login)
            node.appendChild(services)

        host = root.createElement("host")
        host_name = geni_sliver.getName()
        host.setAttribute('name', host_name)
        node.appendChild(host)

    return node


def generateManifest(geni_slice, req_rspec) :

    """
        Returns a manifets rspec that corresponds to the given request rspec
        i.e. annotat the request rspec with information about the resources.
    """
    manifest = Document()                 # Manifest returned by this function

    # Use the request rspec as a model for the manifest i.e. start with the
    # request and add additional information to it to form the manifest
    request = parseString(req_rspec).childNodes[0]
    manifest.appendChild(request)
    request.setAttribute('type', 'manifest')

    # If the request doesn't have xmlns tag, add it
    if not request.hasAttribute("xmlns"):
        request.setAttribute('xmlns', 'http://www.geni.net/resources/rspec/3')

    # If the request doesn't ahve the xmlns:xsi tag, add it
    if not request.hasAttribute('xmlns:xsi'):
        request.setAttribute('xmlns:xsi', \
                                 'http://www.w3.org/2001/XMLSchema-instance')

    # If the request rspec has a xsi:schemaLocation element in the header
    # set the appropriate value to say "manifest" instead of "request"
    if request.hasAttribute('xsi:schemaLocaton') :
        schema_location = request.attributes['xsi:schemaLocation'].value
        schema_location = schema_location.replace('request.xsd', 'manifest.xsd')
        request.setAttribute('xsi:schemaLocation', schema_location)
    else :
        # No attribute for xsi:schemaLocation in request.  Add it to 
        # the manifest
        schema_location = 'http://www.geni.net/resources/rspec/3 http://www.geni.net/resources/rspec/3/manifest.xsd'
        request.setAttribute('xsi:schemaLocation', schema_location)


    # For every child element in the rspec, add manifest related information
    # to the child element.  
    for child in request.childNodes :
        if child.nodeName == 'node' :
            # Set node attributes
            child.setAttribute('exclusive', 'false')

            # Find the VM Object for this node by node name ('client_id') 
            node_name = child.attributes['client_id'].value
            vm_list = geni_slice.getVMs()
            vm_object = None
            for i in range(len(vm_list)) :
                if node_name == vm_list[i].getName() :
                    vm_object = vm_list[i]
                    break
            if vm_object == None :
                config.logger.error('Cannot find information about VM %s' % \
                                        node_name)
                continue   # Go on to next node

            # Set the sliver URN for the node element
            child.setAttribute('sliver_id', vm_object.getSliverURN())
            child.setAttribute('component_id', vm_object.getSliverURN())

            # Set the component_manager_id (this AM's URN) for the node element
            component_manager_id = config.gram_am_urn
            child.setAttribute('component_manager_id', component_manager_id)
            
            # For each child element of node, set appropriate attrbutes.
            # Child elements of node include sliver_type, services, 
            # interface, etc.
            sliver_type_set = False
            login_info_set = False
            login_elements_list = list()
            login_elements_list_unset = True 
            for child_of_node in child.childNodes :
                # First create a new element that has login information
                # for users (if user accounts have been set up)
                user_names = vm_object.getAuthorizedUsers()

                # Create a list that holds login info for each user
                if user_names != None and login_elements_list_unset :
                    login_port = str(vm_object.getSSHProxyLoginPort())
                    my_host_name = \
                        socket.gethostbyaddr(socket.gethostname())[0]
                    for i in range(0, len(user_names)) :
                        login_element = Element('login')
                        login_element.setAttribute('authentication','ssh-keys')
                        login_element.setAttribute('hostname', my_host_name)
                        login_element.setAttribute('port', login_port)
                        login_element.setAttribute('username', user_names[i])
                        login_elements_list.append(login_element)

                login_elements_list_unset = False
                if child_of_node.nodeName == 'sliver_type' :
                    child_of_node.setAttribute('name', vm_object.getVMFlavor())
                    # Look for the <disk_image> child of <sliver_type> and
                    # set it to the correct value
                    for sliver_type_child in child_of_node.childNodes :
                        # Find the child <disk_image>
                        if sliver_type_child.nodeName == 'disk_image' :
                            image_urn = config.image_urn_prefix +  \
                                vm_object.getOSImageName()
                            sliver_type_child.setAttribute('name', image_urn)
                    sliver_type_set = True
                elif child_of_node.nodeName == 'interface' :
                    # Find the NetworkInterface object for this interface
                    nic_name = child_of_node.attributes['client_id'].value
                    nic_list = vm_object.getNetworkInterfaces()
                    for i in range(len(nic_list)) :
                        if nic_name == nic_list[i].getName() :
                            nic_object = nic_list[i]
                            break
                    if nic_object == None :
                        config.logger.error('Cannot find information about network interface %s' % nic_name)
                        continue
                    ip_address = nic_object.getIPAddress()
                    if ip_address != None :
                        ip_addr_elem = manifest.createElement('ip')
                        ip_addr_elem.setAttribute('address', ip_address)
                        ip_addr_elem.setAttribute('type', 'ip')
                        child_of_node.appendChild(ip_addr_elem)
                    mac_address = nic_object.getMACAddress()
                    if mac_address != None :
                        child_of_node.setAttribute('mac_address', mac_address)
                    child_of_node.setAttribute('sliver_id', 
                                               nic_object.getSliverURN())
                elif child_of_node.nodeName == 'services' :
                    # Add a sub-element for the login port for the VM
                    login_info_set = True
                    if len(login_elements_list) > 0 :
                        for i in range(0, len(login_elements_list)) :
                            child_of_node.appendChild(login_elements_list[i])
                        
            if not sliver_type_set :
                # There was no sliver_type set on the manifest because there
                # was no sliver_type element in the request rspec.  We add
                # a new element for sliver_type
                sliver_type = vm_object.getVMFlavor()
                sliver_type_elem = Element('sliver_type')
                sliver_type_elem.setAttribute('name', sliver_type)
                # Create a <disk_image> child for <silver_type>
                disk_image = Element('disk_image')
                image_urn = config.image_urn_prefix + \
                    config.default_OS_image # no image was specified in request
                disk_image.setAttribute('name', image_urn)
                disk_image.setAttribute('os', config.default_OS_type)
                disk_image.setAttribute('version', config.default_OS_version)
                sliver_type_elem.appendChild(disk_image)
                child.appendChild(sliver_type_elem)

            if not login_info_set and len(login_elements_list) != 0 :
                # There was no login information set on the manifest because 
                # there was no services element in the request rspec.  We add
                # a new element for services and a sub-element for login info
                services_element = Element('services')
                for i in range(0, len(login_elements_list)) :
                    services_element.appendChild(login_elements_list[i])
                child.appendChild(services_element)
                
            # Set the hostname element of the manifest (how the VM calls itself)
            host_attribute = Element('host')
            host_attribute.setAttribute('name', node_name)
            child.appendChild(host_attribute)

        elif child.nodeName == 'link' :
            # Find the NetworkLink object for this link
            link_name = child.attributes['client_id'].value
            link_list = geni_slice.getNetworkLinks()
            for i in range(len(link_list)) :
                if link_name == link_list[i].getName() :
                    link_object = link_list[i]
                    break
            child.setAttribute('sliver_id', link_object.getSliverURN())

    return cleanXML(manifest, "OldManifest")

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
def generateAdvertisement(am_urn):

    component_manager_id = am_urn
    component_name = str(uuid.uuid4())
    component_id = 'urn:public:geni:gpo:vm+' + component_name
    exclusive = False
    client_id="VM"

    flavors = open_stack_interface._listFlavors()
    sliver_type = config.default_VM_flavor
    node_types = ""
    for flavor_name in flavors.values():
        node_type = '<node_type type_name="%s"/>' % flavor_name
        node_types = node_types + node_type + "\n"

    images = open_stack_interface._listImages()
#    print "IMAGES = " + str(images)
    image_types = ""
    for image_id in images.keys():
        image_name = images[image_id]
        version = config.default_OS_version
        os = config.default_OS_type
        description = ""
        if config.disk_image_metadata.has_key(image_name):
            metadata = config.disk_image_metadata[image_name]
            if metadata.has_key('os'): os = metadata['os']
            if metadata.has_key('version'): version = metadata['version']
            if metadata.has_key('description'): description = metadata['description']
        disk_image = '<disk_image name="%s" os="%s" version="%s" description="%s" />' % (image_name, os, version, description)
        image_types = image_types + disk_image + "\n"

    available = True

    tmpl = '''  <node component_manager_id="%s"
        client_id="%s"
        component_name="%s"
        component_id="%s"
        exclusive="%s">%s%s<sliver_type name="%s"/>
    <available now="%s"/>
  </node>
  %s
  </rspec>
  '''

    schema_locs = ["http://www.geni.net/resources/rspec/3",
                   "http://www.geni.net/resources/rspec/3/ad.xsd",
                   "http://www.geni.net/resources/rspec/ext/opstate/1",
                   "http://www.geni.net/resources/rspec/ext/opstate/1/ad.xsd"]
    advert_header = '''<?xml version="1.0" encoding="UTF-8"?> 
         <rspec xmlns="http://www.geni.net/resources/rspec/3"                 
                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
       xsi:schemaLocation="%s" type="advertisement">''' % (' '.join(schema_locs))

    stitching = stitching_rspecs.Stitching()
    stitching_advertisement = stitching.generateAdvertisement().toxml()
    result = advert_header + \
        (tmpl % (component_manager_id, client_id, component_name, \
                     component_id, exclusive, node_types, \
                     image_types, \
                     sliver_type, available, stitching_advertisement)) 
    return result
