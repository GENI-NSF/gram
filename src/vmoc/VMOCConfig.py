#!/usr/bin/python

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


import json
import pdb
import sys
from VMOCGlobals import VMOCGlobals

# Class for representing the details of a slice from the
# perspective of the VMOC
# A slice has a name and a list of VLAN/controller pairs 
# {'vlan':vlan, 'controller_url':controller_url}
# (where controller_url may be null)

# Represents the configuration of a VLAN within a slice: its VLAN tag and 
# controller url
class VMOCVLANConfiguration:
    def __init__(self, vlan_tag=None, controller_url=None, attribs=None):
        if attribs != None:
            vlan_tag = attribs['vlan']
            controller_url = attribs['controller_url']
        self._vlan_tag = vlan_tag
        self._controller_url = controller_url

    def getControllerURL(self): return self._controller_url
    def setControllerURL(self, controller_url): 
        self._controller_url = controller_url
    def getControllerURL(self): return self._controller_url
    def getVLANTag(self) :return self._vlan_tag

    def __attr__(self) : 
        return {'vlan':self._vlan_tag, 'controller_url':self._controller_url}
    
    def __str__(self) :
        return str(self._vlan_tag) + " " + str(self._controller_url)

# Represents the configuration of a slice: its ID, 
# and list of vlan/controller pairs
class VMOCSliceConfiguration:
    def __init__(self, slice_id=None, vlan_configs=None,
                 attribs=None):
        if attribs != None:
            slice_id = attribs['slice_id']
            vlan_configs = \
                [VMOCVLANConfiguration(attribs=a) \
                     for a in attribs['vlan_configurations']]
        self._slice_id = slice_id
        self._vlan_configs = vlan_configs
        self._vlans = [vc.getVLANTag() for vc in vlan_configs]
    
    def getSliceID(self) : return self._slice_id
    def getVLANConfigurations(self) : return self._vlan_configs
    def setVLANConfigurations(self, vlan_configs): 
        self._vlan_configs = vlan_configs

    # Is given controller/vlan pair found among the vlan configs of this slice?
    def contains(self, controller_url, vlan):
        found = False
        for vc in self._vlan_configs:
            if vc.getVLANTag() == vlan and \
                    vc.getControllerURL() == controller_url:
                found = True
                break
        return found

    def belongsToSlice(self, vlan_id, src, dst):
        return vlan_id in self._vlans

    def __attr__(self):
        vlan_config_attrs = [vc.__attr__() for vc in self._vlan_configs]
        return {'slice_id' : self._slice_id, 
                'vlan_configurations' : vlan_config_attrs}

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

