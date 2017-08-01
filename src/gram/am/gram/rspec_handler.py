#----------------------------------------------------------------------
# Copyright (c) 2013-2016 Raytheon BBN Technologies
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

	# If this request has a pi_tag, handle it differently
	if node_attributes.has_key('pi_tag'):
	    temp1 = geni_slice._slice_urn.rsplit('+',1)
	    temp2 = temp1[1]
	    # Boolean used to determine if the requested pi_name is in the database
	    flag = 0
#	    print 'PI KEY DETECTED IN ASSOCIATION WITH SLICE: "%s"' % (temp2)
	    # Set the pi_state to match the request
	    if node_attributes.has_key('client_id') :
		node_name = node_attributes['client_id'].value
		pi_list = config.rpi_metadata
		for pi_name in pi_list:
		   if node_name == pi_name:
			flag = 1
			if pi_list[pi_name]['available'].lower() == 'true':
			    pi_list[pi_name]['available'] = 'False'
			    pi_list[pi_name]['owner'] = temp2	
			else :
			    # Resource not available
			    error_string = \
				'Rspec error: Raspberry Pi with name %s is not available' % \
				node_name
			    error_code = constants.UNSUPPORTED
	                    config.logger.error(error_string)
            		    return error_string, error_code, sliver_list, None
		if flag == 0:
		   # Invalid Raspberry Pi name
		   error_string = \
			'Rspec error: Invalid Raspberry Pi name of %s' % node_name
		   error_code = constants.UNSUPPORTED
		   config.logger.error(error_string)
		   return error_string, error_code, sliver_list, None


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

    location_block = ''
    if config.location != None and \
            'latitude' in config.location and 'longitude' in config.location:
        location_block = '<location latitude="%s" longitude="%s"/>' % \
            (config.location['latitude'], 
             config.location['longitude'])

    # Advertise the current state of pi allocation
    pi_list = config.rpi_metadata
    pi_info = config.rpi_info
    pi_result = ""

    # The preset sliver and hardware information that is advertised
#    if pi_info.has_key('hardware_type'): pi_hw = pi_info['hardware_type']
#    if pi_hw.has_key('name'): pi_hw_name = pi_hw['name']
#    if pi_hw.has_key('emulab'): pi_hw_emulab = pi_hw['emulab']
#    pi_hw_block = '  <hardware_type name="%s">\n    <emulab:node_type type_slots="%s" />\n  </hardware_type> \n' \
#	 % (pi_hw_name, pi_hw_emulab)
#    if pi_info.has_key('sliver_type'): pi_sliver = pi_info['sliver_type']
#    if pi_info.has_key('disk_image'): pi_disk = pi_info['disk_image']
#    if pi_disk.has_key('name'): pi_disk_name = pi_disk['name']
#    if pi_disk.has_key('os'): pi_disk_os = pi_disk['os']
#    if pi_disk.has_key('version'): pi_disk_version = pi_disk['version']
#    if pi_disk.has_key('description'): pi_disk_desc = pi_disk['description']
#    pi_sliver_block = '  <sliver_type name="%s">\n    <disk_image name="%s" os="%s" version="%s" description="%s" /> \n  </sliver_type> \n  ' % \
#	(pi_sliver, pi_disk_name, pi_disk_os, pi_disk_version, pi_disk_desc)
    pi_sliver_block = ""
    pi_hw_block = ""
    interface_result = ""

    # The other pi-related information
    for pi_name in pi_list:
	if config.rpi_metadata.has_key(pi_name):
	   pidata = config.rpi_metadata[pi_name]
	   availability = pidata['available']
	   #if availability.lower() == 'true':
	   pidata = config.rpi_metadata[pi_name]
	   interface_result = ""
	   if pidata.has_key('component_id'): component_id = pidata['component_id']
	   if pidata.has_key('exclusive'): exclusive = pidata['exclusive']
	   if pidata.has_key('available'): available = pidata['available']
	   if pidata.has_key('public_ipv4'): public_ipv4 = pidata['public_ipv4']
	   if pidata.has_key('vlan'): vlan = pidata['vlan']  
	   if pidata.has_key('owner'): owner = pidata['owner']  
	   if pidata.has_key('interface'): interface_list = pidata['interface']
	   #for interface in interface_list:
		#interface_data = interface_list[interface]
		#if interface_data.has_key('interface_component_id'): interface_component_id = interface_data['interface_component_id']
		#if interface_data.has_key('role'): role = interface_data['role']
		#if interface_data.has_key('public_ipv4'): interface_ip = interface_data['public_ipv4']
	   	#interface_result = interface_result + '  <interface component_id="%s" role="%s" public_ipv4="%s" /> \n' % \
		#    (interface_component_id, role, interface_ip) 
	   rpi_1 = '\n'+'<node component_manager_id="%s" component_name="%s" component_id="%s" exclusive="%s" available="%s" owner="%s" >' % \
		    (component_manager_id, pi_name, component_id, exclusive, available, owner)
	   pi_result = pi_result + rpi_1 + "\n" + pi_hw_block  + pi_sliver_block + location_block  +\
		 "\n" + interface_result + "</node>"+ "\n"

    # For formatting of the pi_blocks
    pi_block = ''
    pi_block = pi_block + pi_result

    node_block = ''
    stitching_link_block = ""

    POA_header = '<rspec_opstate xmlns="http://www.geni.net/resources/rspec/ext/opstate/1" ' + \
                'aggregate_manager_id=' + '"' + am_urn + '" '
# custome image list
    ci_block = ""

    schema_locs = ["http://www.geni.net/resources/rspec/3",
                   "http://www.geni.net/resources/rspec/3/ad.xsd",
                   "http://hpn.east.isi.edu/rspec/ext/stitch/0.1/",
                   "http://hpn.east.isi.edu/rspec/ext/stitch/0.1/stitch-schema.xsd",
                   "http://www.geni.net/resources/rspec/ext/opstate/1",
                   "http://www.geni.net/resources/rspec/ext/opstate/1/ad.xsd"]
    advert_header = '''<?xml version="1.0" encoding="UTF-8"?> 
         <rspec xmlns="http://www.geni.net/resources/rspec/3" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="%s" type="advertisement">''' % (' '.join(schema_locs))

    stitching_advertisement =""

 # external_refs + '\n' + \ 
    result = advert_header  + '\n' + \
        node_block + '\n' + \
	pi_block + \
        stitching_link_block + '\n' + stitching_advertisement + \
	ci_block + '</rspec>'
       # POA_block + ci_block + '</rspec>'

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

