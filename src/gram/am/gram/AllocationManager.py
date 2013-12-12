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

# A class to manage allocations of resources of a given kind
# Each manager holds a set of resources (objects)
#  and the limit of the number of slivers to which the object may
#      be allocated at once
# And for each resource
#    what slice it is allocated to (None if not allocated)
#    what slivers it is allocated to
#    allocation_time to that slice
# Gives an error when 
#   trying to release a resource from a slice that # doesn't own it
#   trying to release a resource that doesn't exist
#   trying to allocate a resource that doesn't exist
#   trying to allocate a resource that already is allocated to another slice
#   trying to allocate a resource to greater 
#       than a given limited number of slivers

from datetime import datetime
import pdb

class AllocationManager:

    SLICE_ALLOCATION_TAG = 'slice_allocation'
    SLICE_ALLOCATION_TIME_TAG = 'slice_allocation_time'
    SLIVERS_TAG = "slivers"
    ATTRIBUTES_TAG = "attributes";

    def __init__(self, max_slivers):
        self._max_slivers = max_slivers;
        self._resources = dict();

    # Create a record for a new resource being managed
    # Optionally add a set of attributes on the resource for later 
    # query filtering
    def register(self, resource, attributes=dict()):
        resource_record = dict();
        resource_record[self.SLICE_ALLOCATION_TAG] = None;
        resource_record[self.SLICE_ALLOCATION_TIME_TAG] = None;
        resource_record[self.SLIVERS_TAG] = list();
        resource_record[self.ATTRIBUTES_TAG] = attributes;
        self._resources[resource] = resource_record;

        
    # Allocate a resource to a sliver within a slice
    # Check that it exists (is registered)
    # And not already allocated to another slice
    # And not already allocated to same sliver
    # And that the number of slivers to which it is allocated is
    #    not more than 'max_slivers'
    # If so, raise AssertionError
    # Otherwise, update record appropriately
    def allocate(self, resource, slice_urn, sliver_urn):
#        print "In Allocate " + str(resource) + " " + slice_urn + " " + sliver_urn
        assert self._resources.has_key(resource), \
            "Resource not registered: " + str(resource)
        resource_record = self._resources[resource];
        assert resource_record[self.SLICE_ALLOCATION_TAG] == None, \
            "Resource already in a slice: " + str(resource) + " " + \
            resource_record[self.SLICE_ALLOCATION_TAG]
        assert sliver_urn not in resource_record[self.SLIVERS_TAG], \
            "Resource already in sliver: "+ str(resource) + " " + sliver_urn
        assert len(resource_record[self.SLIVERS_TAG]) < self._max_slivers, \
            "Resource allocated to too many slivers: " + str(resource)

        resource_record[self.SLICE_ALLOCATION_TAG] = slice_urn
        resource_record[self.SLICE_ALLOCATION_TIME_TAG] = \
            datetime.now()
        resource_record[self.SLIVERS_TAG].append(sliver_urn)

    # Release a resource from a sliver within a slice
    # Check that it exists (is registered)
    # And belongs to the given slice
    # And the sliver is one of its owners
    # If so, raise AssertionError
    # Otherwise, update record accordingly
    def release(self, resource, slice_urn, sliver_urn):
#        print "Release " + str(resource) + " " + slice_urn + " " + sliver_urn
        assert self._resources.has_key(resource), \
            "Resource not registered: " + str(resource)
        resource_record = self._resources[resource];
        assert resource_record[self.SLICE_ALLOCATION_TAG] == slice_urn, \
            "Resource not member of slice: " + str(resource) + " " + \
            resource_record[self.SLICE_ALLOCATION_TAG]
        assert sliver_urn in resource_record[self.SLIVERS_TAG], \
            "Resource not in sliver: " + str(resource) + " " + sliver_urn

        resource_record[self.SLIVERS_TAG].remove(sliver_urn);
        if(len(resource_record[self.SLIVERS_TAG]) == 0):
            resource_record[self.SLICE_ALLOCATION_TAG] = None
            resource_record[self.SLICE_ALLOCATION_TIME_TAG] = None

    # Dump description of contents to stdout
    def dump(self):
        for key in self._resources.keys():
            rec = self._resources[key];
            print str(key) + " " + \
                str(rec[self.SLICE_ALLOCATION_TAG]) + " " + \
                str(rec[self.SLIVERS_TAG]) + " " + \
                str(rec[self.ATTRIBUTES_TAG])

    # get either allocated or unallocated resources from manager
    # If an optional dictionary is given, only return
    # Those for whom each provided key/value pair is matched
    # for the attribs of the resource
    def getResources(self, allocated, attribs=None):
#        print "getResources: " + str(allocated) + " " + str(attribs)
        values = list();
        for key in self._resources.keys():
            rec = self._resources[key];
            slice_urn = rec[self.SLICE_ALLOCATION_TAG]
            if (allocated and slice_urn is not None) or \
                    (not allocated and slice_urn is None):
                if attribs is None or \
                        self.attributes_match(attribs, \
                                                  rec[self.ATTRIBUTES_TAG]):
                    values.append(key);
#        print "VALUES = " + str(values)
        return values;
        
    # Do all name_value pairs of first (pattern) list 
    # exist in second (value) list?
    def attributes_match(self, pattern, values):
        all_match = True
        for k in pattern.keys():
            v = pattern[k]
            if not values.has_key(k) or values[k] != v:
                all_match = False
                break
#        print "AM: " + str(pattern) + " " + str(values) + " " + str(all_match)
        return all_match
    

# Test procedure
if __name__ == "__main__":
    ATTRIB_TAG = "AT"
    am = AllocationManager(1);
    am.register("A", {ATTRIB_TAG : "A"});
    am.register("B", {ATTRIB_TAG : "B"});
    am.register("C", {ATTRIB_TAG : "C"});
    am.allocate("A", "SLICE", "SLIVER1");
    try:
        am.allocate("A", "SLICE", "SLIVER2");
    except AssertionError:
        print("Caught case of over-allocation");
        pass

    am.allocate("B", "SLICE", "SLIVER");
    try:
        am.allocate("B", "SLICE2", "SLIVER");
    except AssertionError:
        print("Caught case of allocating to two slices");

    try:
        am.release("B", "SLICE2", "SLIVER");
    except AssertionError:
        print("Caught case of releasing from wrong slice");
    
    try:
        am.release("B", "SLICE", "SLIVER2");
    except AssertionError:
        print("Caught case of releasing wrong sliver");

    am.dump();
    attribs = {ATTRIB_TAG : "B"}
    print "Allocated: " + str(am.getResources(True));
    print "Unallocated: " + str(am.getResources(False));
    print "Allocated(B): " + str(am.getResources(True, attribs));
    print "Unallocated(B): " + str(am.getResources(False, attribs));

    am.release("B", "SLICE", "SLIVER");

    try:
        am.allocate("D", "SLICE", "SLIVER");
    except AssertionError:
        print("Caught case of allocating non-existent sliver");

    try:
        am.release("D", "SLICE", "SLIVER");
    except AssertionError:
        print("Caught case of releasing non-existent sliver");


    am.dump();
    print "Allocated: " + str(am.getResources(True));
    print "Unallocated: " + str(am.getResources(False));
    print "Allocated(B): " + str(am.getResources(True, attribs));
    print "Unallocated(B): " + str(am.getResources(False, attribs));



