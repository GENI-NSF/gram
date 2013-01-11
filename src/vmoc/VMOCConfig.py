#! /usr/bin/python

import json
import pdb
import sys
from pox.lib.addresses import EthAddr
from VMOCGlobals import VMOCGlobals

# Class for representing the details of a slice from the
# perspective of the VMOC
# A slice has a controller (possibly None), a name
# A list of VLAN and MACS-for_VLAN

# Represents a list of MACs of network addressable resources (usually VMs)
# on a single VM
class VMOCVlanConfiguration:
    def __init__(self, vlan_id=None, macs=None, attribs=None):
        if attribs != None:
            vlan_id = attribs['vlan_id']
            macs = attribs['macs']
        self._vlan_id = vlan_id
        self._macs = [EthAddr(m) for m in macs] # Make sure these are EthAddr's
        
    def getVlanID(self): return self._vlan_id
    def getMACs(self): return self._macs

    # A VLAN config matches a given VLAN/SRC/DST tuple if:
    # The SRC belongs to the VLAN config
    # The DST belongs to the VLAN config OR is multicast OR is null
    # The VLAN matches the VLAN of the VLAN config or not VMOCGlobals.getVLANTesting()
    def belongsToSlice(self, vlan_id, src, dst):

        src_matches = src in self._macs
        dst_matches = dst is None  or dst in self._macs or dst.isMulticast()
        vlan_matches = vlan_id == self._vlan_id or not VMOCGlobals.getVLANTesting()
        belongs =  src_matches and dst_matches and vlan_matches

#         print "Belongs (Controller) = " + str(self) + " " + str(belongs) + " " + \
#             str(vlan_id) + " " + str(src) + " " + str(dst)
        return belongs

    def __attr__(self):
        return {'vlan_id' : self._vlan_id, 'macs' : self._macs}
    
    def __str__(self):
        return str(self.__attr__())

# Represents the configuration of a slice: its ID, controller URL
# and list of compute nodes
class VMOCSliceConfiguration:
    def __init__(self, slice_id=None, controller_url=None, 
                 vlans=None, attribs=None):
        if attribs != None:
            slice_id = attribs['slice_id']
            controller_url = attribs['controller_url']
            vlans  = [VMOCVlanConfiguration(attribs=v) 
                     for v in attribs['vlans']]
        self._slice_id = slice_id
        self._controller_url = controller_url
        self._vlans = vlans
    
    def getSliceID(self) : return self._slice_id
    def getControllerURL(self) : return self._controller_url
    def setControllerURL(self, controller_url) : self._controller_url = controller_url
    def getVLANs(self) : return self._vlans

    def belongsToSlice(self, vlan_id, src, dst):
        belongs = False
        for vlan in self._vlans:
            if vlan.belongsToSlice(vlan_id, src, dst):
                belongs = True;
                break;
#         print "Belongs (Controller) = " + str(self) + " " + str(belongs) + " " + \
#             str(vlan_id) + " " + str(src) + " " + str(dst)
        return belongs

    def __attr__(self):
        return {'slice_id' : self._slice_id, 
             'controller_url' : self._controller_url,
             'vlans' : [v.__attr__() for v in self._vlans]}

    def __str__(self):
        return str(self.__attr__())

# Read a simple structure (no classes) from a file containing 
# JSON representation
def readFromJSON(filename):
    file = open(filename, 'r')
    json_data = file.read()
    data = json.loads(json_data)
    file.close()
    return data

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print "Usage: python VMOCSliceFlowGenerator slice_config_filename"
        sys.exit()

    slice_config_filename = sys.argv[1]
    slice_config_data = readFromJSON(slice_config_filename)
    slice_config = VMOCSliceConfiguration(attribs=slice_config_data)
    print str(slice_config)

#    generator = VMOCSliceFlowGenerator(fixed_config, slice_config)
#    generator.computeFlows()
