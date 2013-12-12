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

# Top-level singleton class for retrieving/saving state of aggregate  

import json
import os
import pickle
import sys
from Resources import VirtualMachine, NetworkLink, NetworkInterface, Slice
from AllocationManager import AllocationManager
import Archiving

class  AggregateState(object):

    MAX_VLAN_TAG = 10; # Maximum value for vlan tag
    PUBLIC_TAG = "public"
    FLAVOR_TAG = "flavor"
    VLAN_TAGS_TAG = "vlan_tags"
    PUBLIC_IP_ADDRESSES_TAG = "public_IP_addresses"
    FLAVOR_CAPACITIES_TAG = "flavor_capacities"
    PARAMETERS_TAG = "parameters"
    ARCHIVE_DIRECTORY_TAG = "archive_directory"

    # There are two initialization cases:
    # From scratch, using AggregateState constructor: 
    #    initialize from a JSON config file 
    # From a snapshot, using pickle.load
    #   initialize from a pickled version


    # Read config file from JSON config
    def __init__(self, config_filename):

        if config_filename is None: # For reconstructing from data feed
            return;

        config_file = open(config_filename);
        config_data = json.load(config_file);
        config_file.close()

        self._sequence_number = 1; # Counter of transactions and snapshots
        self._slivers_by_urn = dict(); # Map of slivers by their URN

        # Determine if (and where) we're dumping transaction snapshots
        # Create directory if doesn't already exist
        self._archive_directory = None;
        if config_data.has_key(self.ARCHIVE_DIRECTORY_TAG):
            self._archive_directory = config_data[self.ARCHIVE_DIRECTORY_TAG]
            if not os.path.exists(self._archive_directory):
                os.mkdir(self._archive_directory)

        # Parse all public VLAN tags
        self._public_vlan_tags = \
            list(int(i) for i in config_data[self.VLAN_TAGS_TAG])

        # Set up a manager for all VLAN tags
        # MAX_SLICES is maxint since a VLAN may be part of many links
        self._vlan_tag_manager = AllocationManager(sys.maxint);
        for tag in range(self.MAX_VLAN_TAG):
            attribs = {self.PUBLIC_TAG : tag in self._public_vlan_tags}
            self._vlan_tag_manager.register(tag, attribs)

        # Parse all public IP addresses
        self._public_ip_addresses = \
            list(i.encode('utf-8') \
                     for i in config_data[self.PUBLIC_IP_ADDRESSES_TAG]);

        # Set up a manager for public IP addresses
        # MAX_SLICES is 1, since an IP address can only be on one NIC
        self._ip_address_manager = AllocationManager(1);
        for ip in self._public_ip_addresses:
            self._ip_address_manager.register(ip);

        # Parse all flavor capacities
        self._flavor_capacities = dict();
        for fc in config_data[self.FLAVOR_CAPACITIES_TAG]:
            flavor_type = fc.keys()[0].encode('utf-8')
            flavor_capacity = int(fc[flavor_type])
            self._flavor_capacities[flavor_type] = flavor_capacity;

        # Set up a manager for flavor resources
        self._flavor_manager = AllocationManager(1);
        for key in self._flavor_capacities.keys():
            flavor_capacity = self._flavor_capacities[key];
            attrs = {self.FLAVOR_TAG : int(key)};
            for i in range(flavor_capacity):
                resource_name = str(key) + "-" + str(i);
                self._flavor_manager.register(resource_name, attrs);
        self._flavor_allocations = dict(); # sliver_urn => flavor instance

        # Set up parameters as read from config file
        self._parameters = dict();
        params = config_data[self.PARAMETERS_TAG]
        for key in params:
            value = params[key]
            self._parameters[key.encode('utf-8')] = value.encode('utf-8');
            
#        print self._public_vlan_tags
#        print self._public_ip_addresses
#        print self._flavor_capacities
#        print self._parameters


     # List of all currently defined slivers                 
    def getSlivers(self): 
        return self._slivers_by_urn.values()

    # Map of all currently defind slivers by URN
    def getSliversByURN(self):
        return self._slivers_by_urn

    # List of all currently unallocated flavors
    def getUnallocatedFlavors(self): 
        return self._flavor_manager.getResources(False);
     
     # List of all currently available VLAN tags (internal and public)       
    def getUnallocatedVLANTags(public_tag=True): 
        return self._vlan_tag_manager.getResources(False)
    
    # List of all currently unallocated public IP addresses    
    def getUnallocatedPublicIPAddresses(self): 
        attribs = {self.PUBLIC_TAG : public_tag};
        return self._ip_address_manager.getResources(false, attribs);

    # Map of flavor allocations to sliver_URN        
    def getAllocatedFlavors(self): 
        return self._flavor_manager.getResources(True);

    # Map of VLAN tag allocations to sliver_URN                     
    def getAllocatedVLANTags(public_tag=True): 
        attribs = {self.PUBLIC_TAG : public_tag};
        return self._vlan_tag_manager.getResources(True, attribs)
                                    
    # Map of allocated public IP addresses to sliver URN              
    def getAllocatedPublicIPAddresses(self): 
        return self._ip_address_manager.getResources(True);

    # Lookup value of aggregate configuration parameter (e.g. expiration) 
    def getParameter(self, param_name): 
        return self._parameters[param_name];

    # Update internal store of set of slivers (insert or replace) 
    # and update database                                               
    def writeSlivers(self, slivers, slice_urn): 

        # Loop over all slivers, and update for each
        for sliver in slivers:
            sliver_urn = sliver.getComponentID()

            # Remove the sliver if already exists
            if self._slivers_by_urn.has_key(sliver_urn):
                self.deleteSlivers([sliver]);

            # Insert new sliver into slivers list
            self._slivers_by_urn[sliver_urn] = sliver;

            # Update the vlan tag allocation record
            if isinstance(sliver, NetworkLink):
                vlan_tag = sliver.getVLANTag()
                self._vlan_tag_manager.allocate(vlan_tag, \
                                                    slice_urn, sliver_urn)

            # Update the public IP address allocation record
            if isinstance(sliver, NetworkInterface):
                ip_address = sliver.getIPAddress();
                if ip_address in self._public_ip_addresses:
                    self._ip_address_manager.allocate(ip_address, \
                                                          slice_urn, \
                                                          sliver_urn)

            # Update the flavor allocation record
            # If there aren't any more left raise an Assertion Error
            if isinstance(sliver, VirtualMachine):
                flavor = sliver.getFlavor();
                attrs = {self.FLAVOR_TAG : flavor}
                unallocated_of_flavor = \
                    self._flavor_manager.getResources(False, attrs)
                assert len(unallocated_of_flavor) > 0, \
                    "No Allocations left for flavor " + str(flavor)
                allocated_resource = unallocated_of_flavor[0]
                self._flavor_manager.allocate(allocated_resource, \
                                                  slice_urn, sliver_urn)
                self._flavor_allocations[sliver_urn] = allocated_resource

        # Update the database
        self.archive()


    # Remove slivers of given URNs and free all associated resources
    def deleteSlivers(self, slivers, slice_urn):   

        # Loop over all slivers, and update for each
        for sliver in slivers:
            sliver_urn = sliver.getComponentID();

            # Remove the given slivers from the slivers list
            assert self._slivers_by_urn.has_key(sliver_urn), \
                "sliver URN not defined: " + sliver_urn
            del self._slivers_by_urn[sliver_urn];

            # Update the vlan tag allocation counts
            if isinstance(sliver, NetworkLink):
                vlan_tag = sliver.getVLANTag()
                self._vlan_tag_manager.release(vlan_tag, \
                                                   slice_urn, sliver_urn)

            # Update the public IP address lists
            if isinstance(sliver, NetworkInterface):
                ip_address = sliver.getIPAddress();
                if ip_address in self._public_ip_addresses:
                    self._ip_address_manager.release(ip_address, \
                                                         slice_urn, sliver_urn)

        # Update the flavor allocation record
        if isinstance(sliver, VirtualMachine):
            flavor = sliver.getFlavor();
            assert self._flavor_allocations.has_key(sliver_urn), \
                "sliver has undefined flavor: " + str(flavor)
            allocated_resource = self._flavor_allocations[sliver_urn]
            self._flavor_manager.release(allocated_resource, \
                                             slice_urn, sliver_urn)
            del self._flavor_allocations[sliver_urn]

        # Update the database
        self.archive()

    # Save current state of AggregateState object to new pickle file
    # in archive directory
    def archive(self):
        if self._archive_directory is not None:
            filename = self._archive_directory + "/" + \
                "AggregateState-" + str(self._sequence_number) + ".dat"
            file = open(filename, 'wb')
            pickle.dump(self, file)
            file.close()

            filename2 = self._archive_directory + "/" + \
                "AggregateState-" + str(self._sequence_number) + ".json"
            Archiving.write_aggregate_state(filename2, self);
            
#            file = open(filename2, 'wb')
#            json.dump(self, file)
#            file.close()

            self._sequence_number = self._sequence_number + 1


    def __str__(self):
        flavors_image = str(self._flavor_manager.getResources(True))
        vlans_image = str(self._vlan_tag_manager.getResources(True))
        ips_image = str(self._ip_address_manager.getResources(True))
        return "#<GRAM Aggregate State: Flavors " + flavors_image + \
            " VLANs " + vlans_image + \
            " IPs " + ips_image + \
            ">";
    

# Reimport these to make sure the main doesn't get a different
# version of the class than any other modules
from AggregateState import AggregateState
from Resources import VirtualMachine, NetworkLink, NetworkInterface, Slice
from AllocationManager import AllocationManager
if __name__ == "__main__":
    import sys
    if(len(sys.argv) < 2):
        print "Usage: AggregateState.py config.json"
        exit()

    config_file = sys.argv[1]
    agg_state = AggregateState(config_file);

    slice_urn = "SLICE-URN"
    slice = Slice(slice_urn, "SA_URN", "USER_URN", 300L, \
                  '12345', '23456', "<ManifestRspec>");

    vm1 = VirtualMachine(3, 'VM1-URN', slice, 6L, "10.0.0.1", \
                             "VM1", ["foo1"], ["bar1"], \
                             None, ["user1"], 0, 0, 1, 76);
    vm2 = VirtualMachine(4, 'VM2-URN', slice, 7L, "10.0.0.1", \
                             "VM2", ["foo2"], ["bar2"], \
                             None, ["user1"], 0, 0, 2, 77);
    ni1 = NetworkInterface(5, "NL1-URN", slice, 8L, \
                               "NL1", 2, "00:00:00:00:00:02", "10.0.0.2", \
                               vm1, "ETH2", None);
    ni2 = NetworkInterface(6, "NL2-URN", slice, 9L, \
                               "NL2", 3, "00:00:00:00:00:03", "10.0.0.3", \
                               vm2, "ETH3", None);
    nl = NetworkLink(7, 'NI-URN', slice, 7L,\
                         "NI", 3, [ni1, ni2], \
                         '77777', 3)
    ni1.setLink(nl);
    ni2.setLink(nl);
    vm1.setNetworkInterfaces([ni1]);
    vm2.setNetworkInterfaces([ni2]);

    slivers = [vm1, vm2, ni1, ni2, nl]

    print("Writing...");
    agg_state.writeSlivers(slivers, slice_urn)
    print str(agg_state)
#    agg_state._vlan_tag_manager.dump()
#    agg_state._ip_address_manager.dump()
#    agg_state._flavor_manager.dump()


    for sliver in slivers:
        print "Deleting " + str(sliver)
        agg_state.deleteSlivers([sliver], slice_urn)
        print str(agg_state)
#        agg_state._vlan_tag_manager.dump()
#        agg_state._ip_address_manager.dump()
#        agg_state._flavor_manager.dump()



