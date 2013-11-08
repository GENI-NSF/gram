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
import config
import datetime
import json
import logging
import sys
from vlan_pool import VLANPool

logger = logging.getLogger('gram.stitching')

# Module to handle AM side of stitching protocol
#
# The essential design/logic.
# We have a set of outward facing ports on a switch. 
# We advertise these in a stitching advertisement (switch, port, vlans, remote switch)
# We parse and process request rspecs to allow traffic on a given outward facing port
# with a given VLAN tag to a given node/interface
# We create manifests indicating what we have done
# 
# So we need to maintain a structure that manages
#    endpoints (switch port, vlans, remotes)
#    and what currentlly allocated against them.
#    which VLAN is allocated to which slices (and until when)
# Then we create OF flow mods with that duration
#  to say that anything that comes in port X with tag Y goes out port Z
#    where X is the outward facing port (endpoint)
#       and Z is the ingress port of the slice (only one interface
# and vice versa
#
# The request will be to a particular interface on a slice
# so we need to find that interface
#
# The request RSPEC lists a number of nodes (for my component manager plus others)
# and links (with references to interfaces in the nodes)
#  <node
#    <interface client_id="ig-gpo1:if0">
#  </node>
#
#  <link client_id="link-ig-utah1-ig-pgo1">
#    <interface_ref client_id="ig-gpo1:if0" />
#  </link>
#
# Then 
#

# Class that represents a stitching edge point
# Each has its own pool of VLAN allocations
class StitchingEdgePoint:

    def __init__(self, local_switch, port, remote_switch, vlans):
        self._local_switch = local_switch
        self._port = port
        self._remote_switch = remote_switch
        self._vlans = VLANPool(vlans)

    # Return string representation of all available VLAN tags
    def availableVLANs(self): return self._vlans.dumpAvailableVLANs()

    # Select and allocate a tag given a set of suggested and available
    # tags from the request
    def allocateTag(self, request_suggested, request_available):
        request_suggested_values = VLANPool.parseVLANs(request_suggested)
        selected = None
        for candidate in request_suggested_values:
            if self._vlans.isAvailable(candidate):
                selected = candidate
                break

        if not selected:
            if available == 'any':
                my_available = self._vlans._available_vlans
                if len(my_available) > 0:
                    selected = my_available[0]
            else:
                request_available_values = \
                    VLANPool.parseVLANs(request_available)
                for candidate in request_available_values:
                    if self._vlans.isAvailable(candidate):
                        selected = candidate
                        break

        if selected:
            self._vlans.allocate(selected)

        return selected

    def __str__(self):
        return "[EP %s %s %s %s]" % (self._local_switch, self._port, self._remote_switch, self._vlans)


class Stitching:

    def __init__(self):
        data = config.stitching_info
        self._data = data

        # A dictionary indexed by port
        self._edge_points = {}
        for d in data['edge_points']:
            port = d['port']
            ep = StitchingEdgePoint(d['local_switch'], port,
                                    d['remote_switch'], d['vlans'])
            self._edge_points[port] = ep

        self._aggregate_id = data['aggregate_id']
        self._aggregate_url = data['aggregate_url']
        self._namespace = "http://hpn.east.isi.edu/rspec/ext/stitch/0.1"

        # Dictionary of sliver_urn => 
        #      {'vlan_tag' : vlan_tag, 'port' : port, 'expiration' :expiraiton}
        self._reservations = {}

    def parse(self, config_file):
        data = None
        try:
            f = open(config_file, 'r')
            data = f.read()
            f.close()
        except Exception, e:
            mess = "Failed to read stitching config file  " + config_file + " "  + str(e)
            print mess
            logger.info(mess)
            return None

        data = json.loads(data)
        return data

    def isPortOfEdgePoint(self, port):
        return port in self._edge_points

    def getLastUpdateTime(self):
        return datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

    def createChild(self, child_name, parent, doc, text_content = None):
        child = doc.createElement(child_name)
        parent.appendChild(child)
        if text_content:
            content = doc.createTextNode(text_content)
            child.appendChild(content)
        return child

    # Time frame for which a tag is allocated before provisioned
    TEMPORARY_TAG_ALLOCATION = 60

    # Remove all expirated reservations and free tag in VLAN pool
    def removeExpiredReservations(self):
        now = datetime.datetime.now()
        for sliver_urn, reservation in self._reservations.items():
            if 'expiration' in reservation and reservation['expiration'] < now:
                print "Expiring reservation %s %s" % (sliver_urn, reservation)
                port = reservation['port']
                tag = reservation['vlan_tag']
                edge_point = self._edge_points[port]
                edge_point._vlans.free(tag)
                del self._reservations[sliver_urn]

    # Delete allocation of VLAN tag to sliver and port
    def deleteAllocation(self, sliver_id):
        if sliver_id in self._reservations:
            reservation = self._reservations[sliver_id]
            tag = reservation['vlan_tag']
            port_id = reservation['port']
            edge_point = self._edge_points[port_id]
            edge_point._vlans.free(tag)
            del self._reservations[sliver_id]

    def generateAdvertisement(self):
        self.removeExpiredReservations()

        doc = Document()

        base = self.createChild("stitching", doc, doc)
        last_update_time = self.getLastUpdateTime()
        base.setAttribute("lastUpdateTime", last_update_time)
        base.setAttribute("xmlns", self._namespace)
        
        agg = self.createChild("aggregate", base, doc)
        agg.setAttribute("id", self._aggregate_id)
        agg.setAttribute("url", self._aggregate_url)


        stitching_mode = self.createChild("stitchingmode", agg, doc, "chainANDTree")
        scheduled_services = self.createChild("scheduledServices", agg, doc, "false")
        negotiated_services = self.createChild("negotiatedServices", agg, doc, "true")
        
        lifetime = self.createChild("Lifetime", agg, doc)
        start_time = "2013-01-01T00:00:00Z"
        lifetime.setAttribute("start", start_time)
        end_time = "2029-12-31T23:59:59Z"
        lifetime.setAttribute("end", end_time)

        capabilities = self.createChild("capabilities", agg, doc)
        for capability_type in ["consumer", "producer"]:
            self.createChild("capability", capabilities, doc, capability_type)

        for port_value, edge_point in self._edge_points.items():
            local_switch = edge_point._local_switch
            remote_switch = edge_point._remote_switch
            vlans_value = str(edge_point._vlans)

            node = self.createChild("node", agg, doc)
            node.setAttribute("id", local_switch)

            port = self.createChild("port", node, doc)
            port.setAttribute("id", port_value)

            link = self.createChild("link", port, doc)
            link.setAttribute("id", local_switch)
            
            remote_link_id = self.createChild("remoteLinkId", link, doc, remote_switch)

            traffic_engineering_metric = self.createChild("trafficEnginneringMetric", \
                                                              link, doc, "10")

            capacity = self.createChild("capacity", link, doc, "1000000")

            maximumReservableCapacity = self.createChild("maximumReservableCapacity", \
                                                             link, doc, "1000000000")

            minimumReservableCapacity = self.createChild("minimumReservableCapacity", \
                                                             link, doc, "1000000")

            granularity = self.createChild("granularity", link, doc, "1000000")

            scd = self.createChild("switchingCapabilityDescriptor", link, doc)

            sc_type = self.createChild("switchingcapType", scd, doc, "l2sc")

            enc_type = self.createChild("encodingType", scd, doc, "ethernet")

            scsi = self.createChild("switchingCapabilitySpecificInfo", scd, doc)
            
            scsi_l2sc = self.createChild("switchingCapabilitySpecificInfo_L2sc", scsi, doc)

            interface_mtu = self.createChild("interfaceMTU", scsi_l2sc, doc, "9000")

            # Any VLAN
            vlans = self.createChild("vlanRangeAvailability", scsi_l2sc, doc, vlans_value)
            
            xlate = self.createChild("vlanTranslation", scsi_l2sc, doc, "false")

        return doc

    # Notes from conversation with AH:
    # Take the request and copy the stitching portion into the manifest, but change
    # only the parts that are yours (that are links from your advertisement)
    # and replace the vlan tag 
    # Find hops whose links are mine
    # Requested VLAN can be 'any' or a specific value
    # Stitching: Two different component managers (one is me)
    # request_details: parsed from request: My nodes, my links, my hops
    # Allocate = true: return manifest for allocate call
    # Allocate = false: return manifest for provision call
    def generateManifest(self, request, request_details, allocate, sliver_id):

        self.removeExpiredReservations()

        # We perform destructive operations on request to make manifest
        request = request.cloneNode(True)

        request = request.childNodes[0]
        stitching_request = request.getElementsByTagName('stitching')[0]
        stitching_request_paths = stitching_request.getElementsByTagName('path')

        doc = Document()

        base = self.createChild("stitching", doc, doc)
        last_update_time = self.getLastUpdateTime()
        base.setAttribute("lastUpdateTime", last_update_time)
        base.setAttribute("xmlns", self._namespace)

        for path in stitching_request_paths:
            path_id = path.attributes['id'].value
#            print "PID = " + path_id
            manifest_path = self.createChild("path", base, doc)
            manifest_path.setAttribute('id', path_id)
            stitching_request_hops = path.getElementsByTagName('hop')
            for hop in stitching_request_hops:
                hop_id = hop.attributes['id'].value
                manifest_hop = self.createChild("hop", manifest_path, doc)
                manifest_hop.setAttribute('id', hop_id)
                links = hop.getElementsByTagName('link')
                for link in links:
                    link_id = link.attributes['id'].value
                    manifest_link = self.createChild("link", manifest_hop, doc)
                    manifest_link.setAttribute('id', link_id)
                    manifest_link_children = [child for child in link.childNodes] 
                    for i in range(len(manifest_link_children)):
                        child = manifest_link_children[i]
                        manifest_link.appendChild(child)

                    # Allocate a VLAN for manifest based on request
                    # and stick in appropriate field of manifest
                    if link_id in self._edge_points: # One of my ports
                        self.allocateVLAN(link_id, manifest_link, \
                                              allocate, sliver_id)

                next_hop = hop.getElementsByTagName('nextHop')[0]
                manifest_hop.appendChild(next_hop)

        return doc

    # Set the suggested and availability fields of manifest hop_link
    # For a given sliver
    # If 'allocate', pick a new tag (if available)
    # If not 'allocate', use the one that is already allocated
    def allocateVLAN(self, port_id, hop_link, allocate, sliver_id):
        suggested, available = self.parseVLANTagInfo(hop_link)
        edge_point = self._edge_points[port_id]
        if allocate:
            # Temporary - with expiraiton
            selected_vlan = edge_point.allocateTag(suggested,available)
            available = edge_point.availableVLANs()
            expiration = datetime.datetime.now() + \
                datetime.timedelta(seconds=Stitching.TEMPORARY_TAG_ALLOCATION)
            self._reservations[sliver_id] = {'vlan_tag' : selected_vlan,
                                             'port' : port_id,
                                             'expiration' : expiration}
        else:
            reservation = self._reservations[sliver_id]
            selected_vlan = reservation['vlan_tag']
            available = selected_vlan
            # Permanent allcation: remove expiration
            del reservation['expiration']
        self.setVLANTagInfo(hop_link, selected_vlan, available)

    def setVLANTagInfo(self, hop_link, suggested, available):
        availability_nodes = hop_link.getElementsByTagName('vlanRangeAvailability')
        availability_node = availability_nodes[0]
        suggested_nodes = hop_link.getElementsByTagName('suggestedVLANRange')
        suggested_node = suggested_nodes[0]
        suggested_node.childNodes[0].nodeValue = suggested
        availability_node.childNodes[0].nodeValue = available

    def parseVLANTagInfo(self, hop_link):
        availability_nodes = hop_link.getElementsByTagName('vlanRangeAvailability')
        availability_node = availability_nodes[0]
        availability = availability_node.childNodes[0].nodeValue
        suggested_nodes = hop_link.getElementsByTagName('suggestedVLANRange')
        suggested_node = suggested_nodes[0]
        suggested = suggested_node.childNodes[0].nodeValue
        return suggested, availability

    # Is this a stitching rspec, from my perspective?
    # That is, are there multiple component_manager_id's on nodes, one of them me?
    def isStitchingRSpec(self, request_rspec):
        is_stitching = False
        has_my_cmi = False
        has_another_cmi = False
        rspec = request_rspec.childNodes[0]
        for i in range(len(rspec.childNodes)):
            child = rspec.childNodes[i]
            if child.nodeType == Node.ELEMENT_NODE:
                if child.attributes.has_key('component_manager_id'):
                    cmi = child.attributes['component_manager_id'].value
                    is_me = cmi == self._aggregate_id
                    has_my_cmi |= is_me
                    has_another_cmi |= (not is_me)
#        print "has_my_cmi %s has_another_cmi %s" % (has_my_cmi, has_another_cmi)
        return has_my_cmi and has_another_cmi

    # Find the hop that corresponds to an edge point
    def findLocalHop(self, stitching, link_id):
        local_hop = None
        paths = stitching.getElementsByTagName('path')
        for path in paths:
            if path.attributes['id'].value != link_id: continue
            hops = path.getElementsByTagName('hop')
            for hop in hops:
                hop_links = hop.getElementsByTagName('link')
                for hop_link in hop_links:
                    hop_link_id = hop_link.attributes['id'].value
                    if self.isPortOfEdgePoint(hop_link_id):
                        local_hop = hop
                        break
        return local_hop

    # Need to pull out the critical information from request_rspec at allocate time
    # Provision time we create the stitch; Delete  time we remove the stitch
    # 
    # Ignore anything that isn't for me (component_manager_id = my URN)
    # If it is a sitching rspec, find which hop is mind based on link_id interface URN
    #   That's my switch/port and VLAN 
    # 
    #    Compute VLAN (either consume or produce): 
    #        If it is any, I produce. Otherwise I consume)
    #    Unless it is already consumed, else I go through the vlanRangeAvailability
    #
    # Then find the node that is my node and pick the interface of that node
    # Link interface_ref = Node interface
    #   That's my VM / Interface
    # I hold onto this information gathered at allocate time and then
    # Set up the stitch and provision time
    #
    def parseRequestRSpec(self, request_rspec):

        request = request_rspec.childNodes[0]

        nodes = request.getElementsByTagName('node')

        # Find nodes that is mine that has an interface in a stitching link
        my_nodes_by_interface = {}
        for node in nodes:
            cmid = node.attributes['component_manager_id'].value
            if cmid == self._aggregate_id:
                node_id = node.attributes['client_id'].value
                interfaces = node.getElementsByTagName('interface')
                for interface in interfaces:
                    interface_id= interface.attributes['client_id'].value
                    my_nodes_by_interface[interface_id] = node_id

        # Find links that contain my CM
        links = [child for child in request.childNodes if child.nodeName == 'link']
        my_links = []
        for link in links:
            cms = link.getElementsByTagName('component_manager')
            for cm in cms:
                if cm.attributes['name'].value == self._aggregate_id:
                    my_links.append(link)
                    break

        # Find hops that are mine ad involved in link-referenced stitching
        stitching = request.getElementsByTagName('stitching')[0]
        my_hops_by_path_id = {}
        for link in my_links:
            link_id = link.attributes['client_id'].value
            my_hop = self.findLocalHop(stitching, link_id)
            my_hops_by_path_id[link_id] = my_hop

        print "MY NODES and IFS:" + str(my_nodes_by_interface)
        print "MY LINKS:" + str(my_links)
        print "MY HOPS: " + str(my_hops_by_path_id)

        return {"my_nodes_by_interface" : my_nodes_by_interface,
                "my_links" : my_links,
                "my_hops_by_path_id" : my_hops_by_path_id}


if __name__ == '__main__':
    config.initialize('/Users/mbrinn/stitch_testing/config.json')
    stitching = Stitching()
    for ep in stitching._edge_points:
        print str(ep)
    advert = stitching.generateAdvertisement()
    print advert.toprettyxml()

    request_filename = "/Users/mbrinn/stitch_testing/bos-cal-request-rspec.xml"
    request_raw = None
    try:
        f = open(request_filename, 'r');
        request_raw = f.read()
        f.close()
    except Exception,  e:
        print "Can't read request file " + request_filename + " " + str(e)
        sys.exit(0)
    request = parseString(request_raw)

    is_stitching = stitching.isStitchingRSpec(request)
    print("IS STITCHING " + str(is_stitching))

    request_details = stitching.parseRequestRSpec(request)

    sliver_id = "777"

    Stitching.TEMPORARY_TAG_ALLOCATION = 1 
    manifest = stitching.generateManifest(request, request_details, \
                                              True, sliver_id)
    print manifest.toxml()
    import time; time.sleep(2)
    manifest = stitching.generateManifest(request, request_details, \
                                              True, sliver_id)
    print manifest.toxml()
    manifest = stitching.generateManifest(request, request_details, \
                                              False, sliver_id)
    print manifest.toxml()
    manifest = stitching.generateManifest(request, request_details, \
                                              True, sliver_id)
    print manifest.toxml()
    manifest = stitching.generateManifest(request, request_details, \
                                          False, sliver_id)
    print manifest.toxml()

    stitching.deleteAllocation(sliver_id)

    for port, edge_point in stitching._edge_points.items():
        print "Port %s EP %s" % (port, edge_point)




