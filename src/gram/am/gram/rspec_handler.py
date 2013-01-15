
from xml.dom.minidom import *

import config
from resources import Slice, VirtualMachine, NetworkInterface, NetworkLink
import utils

def parseRequestRspec(geni_slice, rspec) :
    """ This function parses a request rspec.   SAY MORE...
        Return:
            None if successful.
            An error string if something went wrong.
    """
        
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

        # Get information about the node from the rspec
        node_attributes = node.attributes
        if node_attributes.has_key('client_id') :
            vm_object.setName(node_attributes['client_id'].value)
        else :
            config.logger.error('Malformed rspec: Node name not specified')
            return 'Malformed rspec: Node name not specified'

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
                config.logger.error('Malformed rspec: Interface name not specified')
                return 'Malformed rspec: Interface name not specified'
            

        # Get the list of services for this node (install and execute services)
        service_list = node.getElementsByTagName('service')
        # First handle all the install items in the list of services requested
        for service in service_list :
            install_list = service.getElementsByTagName('install')
            for install in install_list :
                install_attributes = install.attributes
                if not (install_attributes.has_key('url') and 
                        install_attributes.has_key('install_path')) :
                    config.logger.error('Source URL or destination path missing for install element in request rspec')
                    return 'Source URL or destination path missing for install element in request rspec' 

                source_url = install_attributes['url'].value
                destination = install_attribtues['install_path'].value
                if install_attributes.has_key('file_type') :
                    file_type = install_attributes['file_type'].value
                else :
                    file_type = None
                vm_object.addInstallItem(source_url, destination, file_type)
        
        # Next take care of the execute services requested
        for service in service_list :
            execute_list = service.getElementsByTagName('execute')
            for execute in execute_list :
                execute_attributes = execute.attributes
                if not execute_attributes.has_key('command') :
                    config.logger.error('Command missing for execute element in request rspec')
                    return 'Command missing for execute element in request rspec' 

                exec_command = execute_attributes['command'].value
                if execute_attributes.has_key('shell') :
                    exec_shell = execute_attributes['shell'].value
                else :
                    exec_shell = config.default_execute_shell
                vm_object.addExecuteItem(exec_command, exec_shell)

    # Done getting information about nodes in the rspec.  Now get information
    # about links.
    link_list = rspec_dom.getElementsByTagName('link')
    for link in link_list :
        # Create a NetworkLink object for this link 
        link_object = NetworkLink(geni_slice)

        # Get information about this link from the rspec
        link_attributes = link.attributes
        if link_attributes.has_key('client_id') :
            link_object.setName(link_attributes['client_id'].value)
        else :
            config.logger.error('Malformed rspec: Link name not specified')
            return 'Malformed rspec: Link name not specified'
            
        
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
                config.logger.error('Malformed rspec: Unknown interface_ref %s specified for link %s' % (interface_name, link_object.getName()))
                return 'Malformed rspec: Unknown interface_ref %s specified for link %s' % (interface_name, link_object.getName())

            # Set the interface to point to this link
            interface_object.setLink(link_object)

            # Associate this end point (NetworkInterface) with this link
            link_object.addEndpoint(interface_object)

    return None  # Success


def generateManifest(geni_slice, req_rspec) :


    """
        Returns a tuple that consists of:
           1. The manifest rspec for the specified request rspec (req_rspec)
           2. A list with information about each of the slivers corresponding
              to resources in the request rspec.
    """
    manifest = Document()                 # Manifest returned by this function
    sliver_stat_list = utils.SliverList() # Sliver status list returned 

    # Use the request rspec as a model for the manifest i.e. start with the
    # request and add additional information to it to form the manifest
    request = parseString(req_rspec).childNodes[0]
    manifest.appendChild(request)
    request.setAttribute('type', 'manifest')

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
            for child_of_node in child.childNodes :
                if child_of_node.nodeName == 'sliver_type' :
                    sliver_type = child_of_node.attributes['name'].value
                    child.setAttribute('name', sliver_type)
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
            if not sliver_type_set:
                sliver_type = "virtual-machine"
                sliver_type_attribute = Element('sliver_type')
                sliver_type_attribute.setAttribute('name', sliver_type)
                child.appendChild(sliver_type_attribute)

            # Add this node to the list of slivers in this rspec
            sliver_stat_list.addSliver(vm_object)

        elif child.nodeName == 'link' :
            # Find the NetworkLink object for this link
            link_name = child.attributes['client_id'].value
            link_list = geni_slice.getNetworkLinks()
            for i in range(len(link_list)) :
                if link_name == link_list[i].getName() :
                    link_object = link_list[i]
                    break
            child.setAttribute('sliver_id', link_object.getSliverURN())

            # Add this link to the list of slivers in this rspec
            sliver_stat_list.addSliver(link_object)
            
    manifest = manifest.toprettyxml(indent = '    ')
    config.logger.info('Manifest = %s' % manifest)

    # Create a clean version of the manifest without the extraneous
    # spaces and newlines added by minidom
    clean_manifest = ''
    for line in manifest.split('\n') :
        if line.strip() :
            clean_manifest += line + '\n'

    config.logger.info('Clean manifest = %s' % clean_manifest)

    return clean_manifest, sliver_stat_list.getSliverStatusList()

