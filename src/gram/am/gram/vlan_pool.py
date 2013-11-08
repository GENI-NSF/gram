#----------------------------------------------------------------------
# Copyright (c) 2012 Raytheon BBN Technologies
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

# Class to manage a set of VLAN's
# Letting someone allocate and free one, 
# Verifying if one is allocated, and getting a list of all allocated ones
# There should be one of these on each stitching edge point

class VLANPool:

    def __init__(self, vlan_spec):
        self._all_vlans = VLANPool.parseVLANs(vlan_spec)
        self._available_vlans = [v for v in self._all_vlans]
        self._temporary_allocations = {} # tag => timestamp

    # Parse a comma-separated set of sorted tags into a list of tags
    @staticmethod
    def parseVLANs(vlan_spec):
        ranges = (x.split("-") for x in vlan_spec.split(","))
        return [i for r in ranges for i in range(int(r[0]), int(r[-1]) + 1)]

    def __str__(self): return self.dumpAvailableVLANs()

    # Return available VLAN's as a comma-separated string of sequences
    def dumpAvailableVLANs(self):
        segments = []
        avail = self._available_vlans # Assumed to be sorted
        if len(avail) == 0: return ""
        current_start = avail[0]
        current_end = avail[0]
        for i in range(len(avail)):
            if avail[i] <= current_end+1: 
                # Continue current segment
                current_end = avail[i]
            else:
                # end current segment, start new one
                segments.append((current_start, current_end))
                current_start = avail[i]
                current_end = avail[i]
        segments.append((current_start, current_end))
            
        return ",".join("%d-%d" % (seg[0], seg[1]) for seg in segments)

    # Return list of all available VLAN tags
    def getAvailableVLANs(self):
        return self._available_vlans

    # Return whether a given tag is available
    def isAvailable(self, tag):
        return tag in self._available_vlans

    # Free a given VLAN tag, if in pool and not already allocated
    # If duration_sec is given, only keep allocation for that number of seconds
    # then release
    # If duration_sec was previously given and is no longer given, then 
    # Remove it from temporary state
    # Return boolean indicating success
    def allocate(self, tag, duration_sec=None):
        if tag not in self._all_vlans: return False

        if tag not in self._available_vlans: return False
            
        self._available_vlans.remove(tag)

        return True

    # Free a given VLAN tag, if allowed to be in pool and not already freed
    # Return boolean indicating success
    def free(self, tag):
        if tag not in self._all_vlans: return False
        if tag in self._available_vlans: return False
        self._available_vlans.append(tag)
        self._available_vlans.sort()
        return True

if __name__ == "__main__":
    pool = VLANPool('3-50,60-90')
    print pool.dumpAvailableVLANs()
    print "Alloc 2 = %s " % pool.allocate(2)
    print pool.dumpAvailableVLANs()
    print "Alloc 10 = %s " % pool.allocate(10)
    print pool.dumpAvailableVLANs()
    print "Alloc 10 = %s " % pool.allocate(10)
    print pool.dumpAvailableVLANs()
    print "Alloc 20 = %s " % pool.allocate(20)
    print pool.dumpAvailableVLANs()
    print "Alloc 20 = %s " % pool.allocate(20)
    print pool.dumpAvailableVLANs()
    print "Alloc 89 = %s " % pool.allocate(89)
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
    
    

