#! /usr/bin/python

import json
import pdb
import sys
from pox.lib.addresses import EthAddr
from VMOCGlobals import VMOCGlobals

# Class for representing the details of a slice from the
# perspective of the VMOC
# A slice has a controller (possibly None), a name and a list of VLAN's


# Represents the configuration of a slice: its ID, controller URL
# and list of vlan's
class VMOCSliceConfiguration:
    def __init__(self, slice_id=None, controller_url=None, 
                 vlans=None, attribs=None):
        if attribs != None:
            slice_id = attribs['slice_id']
            controller_url = attribs['controller_url']
            vlans  = [int(v) for v in attribs['vlans']]
        self._slice_id = slice_id
        self._controller_url = controller_url
        self._vlans = vlans
    
    def getSliceID(self) : return self._slice_id
    def getControllerURL(self) : return self._controller_url
    def setControllerURL(self, controller_url) : self._controller_url = controller_url
    def getVLANs(self) : return self._vlans

    def belongsToSlice(self, vlan_id, src, dst):
        return vlan_id in self._vlans

    def __attr__(self):
        return {'slice_id' : self._slice_id, 
             'controller_url' : self._controller_url,
             'vlans' : self._vlans}

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
