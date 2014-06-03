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

import threading
import config

# Class to manage a set of VLAN's
# Letting someone allocate and free one, 
# Verifying if one is allocated, and getting a list of all allocated ones
# There should be one of these on each stitching edge point

class VLANPool:

    ANY_TAG = 'any'

    def __init__(self, vlan_spec, name):
        self._lock = threading.RLock()
        self._all_vlans = VLANPool.parseVLANs(vlan_spec)
        self._available_vlans = [v for v in self._all_vlans]
        self._temporary_allocations = {} # tag => timestamp
        self._name = name

    # Parse a comma-separated set of sorted tags into a list of tags
    # if 'any' return 'any'
    @staticmethod
    def parseVLANs(vlan_spec):
        vlan_spec = vlan_spec.strip()
        if vlan_spec == VLANPool.ANY_TAG:
            return vlan_spec
        ranges = (x.split("-") for x in vlan_spec.split(","))
        return [i for r in ranges for i in range(int(r[0]), int(r[-1]) + 1)]

    # Turn a sorted list of tags into a string synposis of the tags
    # hyphen-separated between groups, comma-separated between gaps
    @staticmethod
    def dumpVLANs(tags):
        segments = []
        if len(tags) == 0: return ""
        current_start = tags[0]
        current_end = tags[0]
        for i in range(len(tags)):
            if tags[i] <= current_end+1: 
                # Continue current segment
                current_end = tags[i]
            else:
                # end current segment, start new one
                segments.append((current_start, current_end))
                current_start = tags[i]
                current_end = tags[i]
        segments.append((current_start, current_end))
            
        return ",".join("%d-%d" % (seg[0], seg[1]) for seg in segments)



    # Produce list of tags intersecting the available vlans with given set
    # if given set is ANY, return available list. Otherwise compute intersection
    def intersectAvailable(self, tags):
        if tags == VLANPool.ANY_TAG:
            return self._available_vlans
        intersection = [tag for tag in tags if tag in self._available_vlans]
        return intersection

    def __str__(self): return self.dumpAvailableVLANs()

    # Return available VLAN's as a comma-separated string of sequences
    def dumpAvailableVLANs(self):
        return VLANPool.dumpVLANs(self._available_vlans)

    # Return list of all VLAN tags for this pool (allocated and not)
    def getAllVLANs(self):
        return self._all_vlans

    # Return list of all available VLAN tags
    def getAvailableVLANs(self):
        return self._available_vlans

    # Return whether a given tag belongs to this pool but is allocated
    def isAllocated(self, tag):
        return tag in self._all_vlans and tag not in self._available_vlans

    # Return whether a given tag is available
    def isAvailable(self, tag):
        return tag in self._available_vlans

    # Allocate a VLAN tag.
    # If the tag is specified, allocate it if available otherwise fail
    # If not specified (None) return the first available or fail if none left
    # Return boolean indicating success
    def allocate(self, tag):
        with self._lock:  # Thread-safe concurrent access to pool
            # If tag not specified, pick the first from the list
            if not tag:
                if len(self._available_vlans) > 0:
                    tag = self._available_vlans[0]
                else:
                    return False, None

            if tag not in self._all_vlans: return False, None

            if tag not in self._available_vlans: return False, None
            
            self._available_vlans.remove(tag)

            config.logger.info( "Allocated %d from VLAN pool %s" % \
                                    (tag, self._name))

            return True, tag

    # Free a given VLAN tag, if allowed to be in pool and not already freed
    # Return boolean indicating success
    def free(self, tag):
        with self._lock: # Thread-safe concurrent access to pool
            if tag not in self._all_vlans: return False
            if tag in self._available_vlans: return False
            self._available_vlans.append(tag)
            self._available_vlans.sort()
            config.logger.info("Freed %d to VLAN pool %s" % (tag, self._name))
            return True

if __name__ == "__main__":
    pool = VLANPool('3-50,60-90', 'FOO')
    print pool.dumpAvailableVLANs()

    success, tag = pool.allocate(2)
    print "Alloc 2 = %s " % tag
    print pool.dumpAvailableVLANs()

    success, tag = pool.allocate(10)
    print "Alloc 10 = %s " % tag
    print pool.dumpAvailableVLANs()

    success, tag = pool.allocate(10)
    print "Alloc 10 = %s " % tag
    print pool.dumpAvailableVLANs()

    success, tag = pool.allocate(20)
    print "Alloc 20 = %s " % tag
    print pool.dumpAvailableVLANs()

    success, tag = pool.allocate(20)
    print "Alloc 20 = %s " % tag
    print pool.dumpAvailableVLANs()

    success, tag = pool.allocate(89)
    print "Alloc 89 = %s " % tag
    print pool.dumpAvailableVLANs()

    print "Free 88 = %s " % pool.free(88)
    print pool.dumpAvailableVLANs()
    print "Free 88 = %s " % pool.free(89)
    print pool.dumpAvailableVLANs()
    print "Free 10 = %s " % pool.free(10)
    print pool.dumpAvailableVLANs()
    print "Free 2 = %s " % pool.free(2)
    print pool.dumpAvailableVLANs()
    print "Free 20 = %s " % pool.free(20)
    print pool.dumpAvailableVLANs()

    tags = pool.intersectAvailable(VLANPool.parseVLANs('1-10'))
    print "TAGS = %s" % tags

    tags = pool.intersectAvailable(VLANPool.ANY_TAG)
    print "TAGS = %s" % tags
    
    

