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
#
# Manages list of all slices and associated controller (by URL)
# register_slice(slice_config, url)
# unregister_slice(slice_id)
# lookup_slices(url) => slice_configs
# lookup_slice_config(slice_id) => slice_config

from VMOCConfig import VMOCSliceConfiguration, VMOCVLANConfiguration
import pdb
import threading

class VMOCSliceRegistry:

    # Lock on the registry (class variable)
    _lock = threading.RLock()

    # Static class instance
    _instance = None;

    def __init__(self):
        self._slices_by_url = dict()
        self._slice_by_slice_id = dict()
        self._slice_by_vlan = dict()
        VMOCSliceRegistry._instance = self
        

    # Return list of registered slices
    def get_slice_configs(self):
        return self._slice_by_slice_id.values()

    # Is given slice config registered?
    def is_registered(self, slice_config):
        slice_id = slice_config.getSliceID()
        return self._slice_by_slice_id.has_key(slice_id) 

    # Register slice configuration by id and URL
    def register_slice(self, slice_config):
        slice_id = slice_config.getSliceID()

        self._slice_by_slice_id[slice_id] = slice_config

        for vc in slice_config.getVLANConfigurations():
            url = vc.getControllerURL()
            vlan = vc.getVLANTag()
            assert not self._slices_by_url.has_key(url) or \
                not slice_config in self._slices_by_url[url]
            if not self._slices_by_url.has_key(url):
                self._slices_by_url[url] = []
            self._slices_by_url[url].append(slice_config)

            self._slice_by_vlan[vlan] = slice_config


    # Remove information about slice associated with given slice ID
    def unregister_slice(self, slice_id):
        assert self._slice_by_slice_id.has_key(slice_id)
        slice_config = self._slice_by_slice_id[slice_id]

        del self._slice_by_slice_id[slice_id]

        for vc in slice_config.getVLANConfigurations():
            url = vc.getControllerURL()
            vlan = vc.getVLANTag()
            assert self._slices_by_url.has_key(url)
            self._slices_by_url[url].remove(slice_config)
            assert self._slice_by_vlan.has_key(vlan)
            del self._slice_by_vlan[vlan]

    # Lookup slice associated with controller url
    def lookup_slices_by_url(self, controller_url):
        slices = None
        if self._slices_by_url.has_key(controller_url):
            slices = self._slices_by_url[controller_url]
        return slices

    # Lookup slice config by slice_id
    def lookup_slice_config_by_slice_id(self, slice_id):
        config = None
        if self._slice_by_slice_id.has_key(slice_id):
            config = self._slice_by_slice_id[slice_id]
        return config

    # Lookup slice config by vlan tag
    def lookup_slice_config_by_vlan(self, vlan_tag):
        config = None
        if self._slice_by_vlan.has_key(vlan_tag):
            config = self._slice_by_vlan[vlan_tag]
        return config

    # Dump contents of registry
    def dump(self, print_results=False):
        image = "VMOC Slice Registry: " + "\n"
        for slice_id in self._slice_by_slice_id.keys():
            image += slice_id + ": " + str(self._slice_by_slice_id[slice_id]) + "\n"
        for controller_url in self._slices_by_url.keys():
            image += str(controller_url) + "\n "
            for slice in self._slices_by_url[controller_url]:
                image += "   " + str(slice) + "\n"
        for vlan in self._slice_by_vlan.keys():
            image += str(vlan) + ": " + str(self._slice_by_vlan[vlan]) + "\n"

        if print_results:
            print image
        return image

# Static interface

__static_isntance = VMOCSliceRegistry()

def slice_registry_get_slice_configs():
    with VMOCSliceRegistry._lock:
        return VMOCSliceRegistry._instance.get_slice_configs()

# Register slice configuration with slice registry
def slice_registry_register_slice(slice_config):
    with VMOCSliceRegistry._lock:
        VMOCSliceRegistry._instance.register_slice(slice_config)
    
# Remove slice configuration with slice registry
def slice_registry_unregister_slice(slice_id):
    with VMOCSliceRegistry._lock:
        VMOCSliceRegistry._instance.unregister_slice(slice_id)

# Lookup slice_configs associated with given URL
def slice_registry_lookup_slices_by_url(controller_url):
    with VMOCSliceRegistry._lock:
        return VMOCSliceRegistry._instance.lookup_slices_by_url(controller_url)

# Lookup slice_config associated with given slice_id
def slice_registry_lookup_slice_config_by_slice_id(slice_id):
    with VMOCSliceRegistry._lock:
        return VMOCSliceRegistry._instance.lookup_slice_config_by_slice_id(slice_id)

# Lookup slice_config for given vlan tag
def slice_registry_lookup_slice_config_by_vlan(vlan_tag):
    with VMOCSliceRegistry._lock:
        return VMOCSliceRegistry._instance.lookup_slice_config_by_vlan(vlan_tag)

# Is given slice configuraiton already registered (by name and url)?
def slice_registry_is_registered(slice_config):
    with VMOCSliceRegistry._lock:
        return VMOCSliceRegistry._instance.is_registered(slice_config)

# Dump contents of slice registry
def slice_registry_dump(print_results=False):
    with VMOCSliceRegistry._lock:
        return VMOCSliceRegistry._instance.dump(print_results)


if __name__ == "__main__":
    slice_id1 = 'S1'
    slice_id2 = 'S2'
    controller1 = 'http://localhost:9001'
    controller2 = 'http://localhost:9002'
    vlan1 = VMOCVLANConfiguration(vlan_tag=100, controller_url=None)
    vlan2 = VMOCVLANConfiguration(vlan_tag=101, controller_url=controller1)
    vlans_full = [vlan1, vlan2]
    vlans_empty = []
    slice1 = VMOCSliceConfiguration(slice_id1, vlans_full)
    slice2 = VMOCSliceConfiguration(slice_id2, vlans_empty)
    slice_registry_register_slice(slice1)
    slice_registry_register_slice(slice2)
    slice_registry_dump(True)
    print "LOOKUP S1 " + str(slice_registry_lookup_slice_config_by_slice_id(slice_id1))
    print "LOOKUP S2 " + str(slice_registry_lookup_slice_config_by_slice_id(slice_id2))
    print "LOOKUP C1 " + str(slice_registry_lookup_slices_by_url(controller1))
    print "LOOKUP C2 " + str(slice_registry_lookup_slices_by_url(controller2))
    slice_registry_unregister_slice(slice_id2)
    slice2a = VMOCSliceConfiguration(slice_id2, vlans_empty)
    slice_registry_register_slice(slice2a)
    slice_registry_dump(True)


    
    
    
    




    
