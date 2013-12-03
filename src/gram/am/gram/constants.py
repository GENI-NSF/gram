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

# A series of constants for GRAM-internal processing
# These things are not to be changed, even at config time.
# Any thing that might be user configurable should be in config.py

# Allocation states for slivers
unallocated = 'geni_unallocated'
allocated = 'geni_allocated'
provisioned = 'geni_provisioned'

# Operational states for slivers
notready = 'geni_notready'
configuring = 'geni_configuring'
ready = 'geni_ready'
failed = 'geni_failed'
stopping = 'geni_stopping'


# Error codes returned by this aggregate manager
# GENI standard codes.
SUCCESS = 0
REQUEST_PARSE_FAILED = 1        # aka BADARGS
UNKNOWN_SLICE = 12              # aka SEARCHFAILED
UNSUPPORTED = 13                
SLICE_ALREADY_EXISTS = 17       # aka ALREADYEXISTS
OUT_OF_RANGE = 19               # typically for time mismatches
VLAN_UNAVAILABLE = 24

# GRAM specific codes
OPENSTACK_ERROR = 100

# We manage the IP address space for the control and management networks
control_netmask = "255.255.255.0"
management_netmask = "255.255.255.0"
