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
        # Create a VirtualMachine object for this node and add it to the list
        # of virtual machines that belong to this slice
        vm_object = VirtualMachine(geni_slice)
        sliver_list.append(vm_object)

        # Get information about the node from the rspec
        node_attributes = node.attributes
        if node_attributes.has_key('client_id') :
            vm_object.setName(node_attributes['client_id'].value)
        else :
            error_string = 'Malformed rspec: Node name not specified' 
            config.logger.error(error_string)
            return error_string, sliver_list, None

        # Set optional flavor of the node
        if node_attributes.has_key('flavor') :
            vm_object.setVMFlavor(node_attributes['flavor'].value)

        # Alternatively, get flavor from the sliver_type
        sliver_type_list = node.getElementsByTagName('sliver_type')
        for sliver_type in sliver_type_list:
            if sliver_type.attributes.has_key('name'):
                sliver_type_name = sliver_type.attributes['name'].value
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
                disk_image_name = disk_image.attributes['name'].value
                disk_image_uuid = \
                    open_stack_interface._getImageUUID(disk_image_name)
                if disk_image_uuid:
                    config.logger.info("DISK = " + str(disk_image_name) + \
                                           " " + str(disk_image_uuid))
                    vm_object.setOSImageName(disk_image_name)
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
            sliver_list.append(interface_object)
            vm_object.addNetworkInterface(interface_object)
            
            # Get information about this network interface from rspec
            interface_attributes = interface.attributes
            if interface_attributes.has_key('client_id') :
                interface_object.setName(interface_attributes['client_id'].value)
            else :
                error_string = 'Malformed rspec: Interface name not specified'
                config.logger.error(error_string)
                return error_string, sliver_list, None

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
        # Create a NetworkLink object for this link 
        link_object = NetworkLink(geni_slice)
        sliver_list.append(link_object)

        # Get information about this link from the rspec
        link_attributes = link.attributes
        if link_attributes.has_key('client_id') :
            link_object.setName(link_attributes['client_id'].value)
        else :
            error_string = 'Malformed rspec: Link name not specified'
            config.logger.error(error_string)
            return error_string, sliver_list, None
        
        # Get the end-points for this link.  Each end_point is a network
        # interface
        end_points = link.getElementsByTagName('interface_ref')
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

    controllers = rspec_dom.getElementsByTagName('openflow:controller')
    if len(controllers) > 0:
        controller_node = controllers[0]
        controller = controller_node.attributes['url'].value

    return error_string, sliver_list, controller


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
            sliver_type_set=False
            login_info_set = False
            for child_of_node in child.childNodes :
                # First create a new element that has login information
                # for users (if user accounts have been set up)
                user_names = vm_object.getAuthorizedUsers()

                # Create a list that holds login info for each user
                login_elements_list = list() 
                if user_names != None :
                    login_port = str(vm_object.getSSHProxyLoginPort())
                    my_host_name = \
                        socket.gethostbyaddr(socket.gethostname())[0]
                    for i in range(0, len(user_names)) :
                        login_element = Element('login')
                        login_element.setAttribute('authentication', 'ssh-keys')
                        login_element.setAttribute('hostname', my_host_name)
                        login_element.setAttribute('port', login_port)
                        login_element.setAttribute('username', user_names[i])
                        login_elements_list.append(login_element)
                        
                if child_of_node.nodeName == 'sliver_type' :
                    # sliver_type = child_of_node.attributes['name'].value
                    child_of_node.setAttribute('name', 'virtual-machine')
                    # Look for the <disk_image> child of <sliver_type> and
                    # set it to the correct value
                    for sliver_type_child in child_of_node.childNodes :
                        # Find the child <disk_image>
                        if sliver_type_child.nodeName == 'disk_image' :
                            image_urn = \
                                'urn:publicid:IDN+emulab.net+image+emulab-ops:'
                            image_urn += config.default_OS_image
                            sliver_type_child.setAttribute('name', image_urn)
                            sliver_type_child.setAttribute('os', 
                                                         config.default_OS_type)
                            sliver_type_child.setAttribute('version', 
                                                      config.default_OS_version)
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
                    for i in range(0, len(login_elements_list)) :
                        child_of_node.appendChild(login_elements_list[i])
                        
            if not sliver_type_set :
                # There was no sliver_type set on the manifest because there
                # was no sliver_type element in the request rspec.  We add
                # a new element for sliver_type
                sliver_type = "virtual-machine"
                sliver_type_elem = Element('sliver_type')
                sliver_type_elem.setAttribute('name', sliver_type)
                # Create a <disk_image> child for <silver_type>
                disk_image = Element('disk_image')
                image_urn =  'urn:publicid:IDN+emulab.net+image+emulab-ops:'
                image_urn += config.default_OS_image
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

    manifest = manifest.toprettyxml(indent = '    ')
    config.logger.info('Manifest = %s' % manifest)

    # Create a clean version of the manifest without the extraneous
    # spaces and newlines added by minidom
    clean_manifest = ''
    for line in manifest.split('\n') :
        if line.strip() :
            clean_manifest += line + '\n'

    config.logger.info('Clean manifest = %s' % clean_manifest)

    return clean_manifest

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
  </node></rspec>
  '''

    schema_locs = ["http://www.geni.net/resources/rspec/3",
                   "http://www.geni.net/resources/rspec/3/ad.xsd",
                   "http://www.geni.net/resources/rspec/ext/opstate/1",
                   "http://www.geni.net/resources/rspec/ext/opstate/1/ad.xsd"]
    advert_header = '''<?xml version="1.0" encoding="UTF-8"?> 
         <rspec xmlns="http://www.geni.net/resources/rspec/3"                 
                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
       xsi:schemaLocation="%s" type="advertisement">''' % (' '.join(schema_locs))
    result = advert_header + \
        (tmpl % (component_manager_id, client_id, component_name, \
                     component_id, exclusive, node_types, \
                     image_types, \
                     sliver_type, available)) 
    return result
