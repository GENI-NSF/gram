#! /usr/bin/python

import json
import sys

# Class to create a list of flow-mod entries
# for each switch in a configuration to establish
# rules for which VM's can communicate to which VM's and by
# which ports/switches
class VMOCSliceFlowGenerator :

    def __init__(self, fixed_config, slice_config):
        self._fixed_config = fixed_config
        self._slice_config = slice_config

    def getFixedConfig(self) : return self._fixed_config
    def getSliceConfig(self) : return self._slice_config

    # Compute flows for each switch that cover traffic between
    # nodes of a slice
    def computeFlows(self):
#        print "FIXED = " + str(self.getFixedConfig())
#        print "SLICE = " + str(self.getSliceConfig())

        # For every switch, need to write a flow rule
        # that shows how each node-to-node path 
        # SRC=<src MAC> DEST=<dst MAC> port=<out port
        for switch  in self.getFixedConfig().getSwitches():
            print "SWITCH DPID : " + str(switch.getDPID())
            for src in self.getSliceConfig().getNodes():
                for dest in self.getSliceConfig().getNodes():
                    if src == dest: continue
                    port = self.computeOutPort(switch, src, dest)
                    if port != None:
                        print "    SRC %s DST %s PORT %d" % \
                            (src.getMAC(), dest.getMAC(), port)

    # For a given switch, what port should traffic from SRC to DEST go out?
    def computeOutPort(self, switch, src, dest, excluding = []):
        # If the switch connects directly to the DEST node, 
        # return the connecting port
        dest_switch_dpid = dest.getSwitchDPID()
        if dest_switch_dpid == switch.getDPID():
            return dest.getPort()

        # If this switch is on the exluded list (we've already traversed it)
        # return None
        if switch.getDPID() in excluding: return None

        # Otherwise, go through all the switches that this switch
        # Connects to (excluding self) and previous exclusions
        # If any connect to DEST, use the port that led to that connection
        excluding_with_switch = [e for e in excluding]
        excluding_with_switch.append(switch.getDPID())
        for link in switch.getLinks():
            link_dpid = link.getSwitchDPID()
            link_switch = self.getFixedConfig().lookupSwitch(link_dpid)
            out_port = self.computeOutPort(link_switch, src, dest, \
                                               excluding_with_switch)
            if out_port != None:
                return link.getSwitchPort()
                
        return None

# Fixed (slice-independent) configuration information
# The list of switches (internally maintained in a table hashed by DPID)
class VMOCFixedConfiguration:
    def __init__(self, switches):
        self._switches = switches
        self._switches_by_dpid = {}
        for sw in switches:
            self._switches_by_dpid[sw._dpid] = sw

    def getSwitches(self): return self._switches

    def lookupSwitch(self, dpid):
        return self._switches_by_dpid[dpid];

    def __str__(self):
        switches_image = ""
        for sw in self._switches:
            switches_image += str(sw)
        return switches_image

# Represents the configuration of a switch in the fixed (slice-independent)
# configuration
# Contains the DPID of the switch and list of links to other switches
class VMOCSwitchConfiguration:
    def __init__(self, dpid=None, links=None, attribs=None):
        if attribs != None:
            dpid = attribs['dpid']
            links = [VMOCLinkConfiguration(attribs=l)
                     for l in attribs['links']]
        self._dpid = dpid
        self._links = links
        self._links_by_switch_dpid = {}
        for link in links:
            self._links_by_switch_dpid[link._switch_dpid] = link

    def getDPID(self) : return self._dpid
    def getLinks(self) : return self._links
    
    def lookupLink(self, switch_dpid): 
        return self._links_by_switch_dpid[switch_dpid]

    def __str__(self):
        links_image = ""
        for l in self._links:
            links_image += str(l)
        return "[%d %s]" % (self._dpid, links_image)

# Represents the link between a given switch and a connected switch
# in the fixed (slice-independent) configuration.
# For each link, the DPID of a connected switch and port through which it 
# is connected to this switch.
class VMOCLinkConfiguration:
    def __init__(self, switch_dpid=None, switch_port=None, attribs=None):
        if attribs != None:
            switch_dpid = int(attribs['id'])
            switch_port = int(attribs['port'])
        self._switch_dpid = switch_dpid
        self._switch_port = switch_port

    def getSwitchDPID(self): return self._switch_dpid
    def getSwitchPort(self): return self._switch_port

    def __str__(self):
        return "[%d %d]" % (self._switch_dpid, self._switch_port)

# Represents a compute node (VM) in a  slice configuration
# Contains its MAC address, the DPID of switch to which it is connected
# and port on that switch
class VMOCNodeConfiguration:
    def __init__(self, mac=None, switch_dpid=None, port=None, attribs=None):
        if attribs != None:
            mac = attribs['mac']
            switch_dpid = attribs['switch']
            port = attribs['port']
        self._mac = mac
        self._switch_dpid = switch_dpid
        self._port = port

    def getMAC(self) : return self._mac
    def getSwitchDPID(self) : return self._switch_dpid
    def getPort(self) : return self._port

    def __str__(self):
        return "[%s %d %d]" % (self._mac, self._switch_dpid, self._port)

# Represents the configuration of a slice: its ID, controller URL, VLAN_ID
# and list of compute nodes
class VMOCSliceConfiguration:
    def __init__(self, slice_id=None, controller_url=None, vlan_id=None, 
                 nodes=None, attribs=None):
        if attribs != None:
            slice_id = attribs['slice_id']
            controller_url = attribs['controller_url']
            vlan_id = attribs['vlan_id']
            nodes = [VMOCNodeConfiguration(attribs=n) 
                     for n in attribs['nodes']]
        self._slice_id = slice_id
        self._controller_url = controller_url
        self._vlan_id = vlan_id
        self._nodes = nodes
    
    def getSliceID(self) : return self._slice_id
    def getControllerURL(self) : return self._controller_url
    def getVlanID(self) : return self._vlan_id
    def getNodes(self) : return self._nodes

    def __str__(self):
        nodes_image = ""
        for node in self._nodes:
            nodes_image += str(node)
        return "[%s %s %d %s]" % (self._slice_id, self._controller_url, \
                                      self._vlan_id, nodes_image)


# Read a simple structure (no classes) from a file containing 
# JSON representation
def readFromJSON(filename):
    file = open(filename, 'r')
    json_data = file.read()
    data = json.loads(json_data)
    file.close()
    return data

if __name__ == "__main__":

    if len(sys.argv) < 3:
        print "Usage: python VMOCSliceFlowGenerator fixed_config_filename slice_config_filename"
        sys.exit()

    fixed_config_filename = sys.argv[1]
    fixed_config_data = readFromJSON(fixed_config_filename)
    switches = [VMOCSwitchConfiguration(attribs=s)
                for s in fixed_config_data]
    fixed_config = VMOCFixedConfiguration(switches)
    slice_config_filename = sys.argv[2]
    slice_config_data = readFromJSON(slice_config_filename)
    slice_config = VMOCSliceConfiguration(attribs=slice_config_data)

    generator = VMOCSliceFlowGenerator(fixed_config, slice_config)
    generator.computeFlows()
