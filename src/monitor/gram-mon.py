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

from gram.am.gram import open_stack_interface
from gram.am.gram import Archiving
from gram.am.gram import config
from gram.am.gram import stitching
import sys
import getopt
import gmoc
import os
import getpass
import time
import uuid
import re

# all these variables should be in config.json  +++++
# submission staging server
GMOC_REL_URL='https://gmoc-db2.grnoc.iu.edu/xchange/webservice.pl'
# submission production server
# GMOC_REL_URL=https://gmoc-db.grnoc.iu.edu/xchange/webservice.pl
# GMOC short name which is your username for authenticated monitoring data submission
SITENAME='GRAM_BOS_CAMBRIDGE'
# GMOC short name of organization which manages your aggregate 
ORGNAME='GRAMGPO'
# urn:publicid:IDN+gmoc.geni.net+organization+GRAMGPO
# GMOC short name of "POP"/lab where your aggregate is located
POPNAME='BOS_CAMBRIDGE'
#urn:publicid:IDN+gmoc.geni.net+pop+BOS_CAMBRIDGE
AMTYPE='gram'
MONUSERNAME='gram' 
MONPASSWORD='gramMonitoring'
MONDEBUGLEVEL= gmoc.GMOC_DEBUG_VERBOSE  
# all these variables should be in config.json  +++++

def usage():
  print "As a service daemon:"
  print "\tgram-mon.py"
  print "As a tool to help map information to a sliver or slice:"
  print '\tgram-mon.py -i <ipaddress>'
  print '\tgram-mon.py -m <macaddr>'
  print '\tgram-mon.py -v <vlantag>'

def printDiagInfo(curSlice, curSliver):
  print "\tSlice URN : " + curSlice.getSliceURN()
  print "\tUser URN  : " + curSliver.getUserURN()
  slivers = curSlice.getAllSlivers()
  for k, v in slivers.iteritems():
    if isinstance(v, Archiving.VirtualMachine):
      print "\tVM UUID   : " + v.getUUID() + " on " + v.getHost() 
    elif isinstance(v, Archiving.NetworkLink):
      print "\tLink UUID : " + v.getUUID()
    elif isinstance(v, Archiving.NetworkInterface):
      print "\tNIC UUID  : " + v.getUUID()

def monitor(parms):

 try:
   opts, args = getopt.getopt(parms,"hdv:m:i:", ["vlan=", "mac=", "ip="])

 except getopt.GetoptError:
   print "gram_mon.py: Error parsing args"
   sys.exit(2)

 found = False
 sip = None
 smac = None
 svlan = None

 for opt, arg in opts:
#   print opt, arg
   if opt == '-h':
     usage()
     sys.exit()
   elif opt in ("-i", "--ip"):
     sip = arg
     print "Searching for Slice Information for ipaddr " + sip
   elif opt in ("-m", "--mac"):
     smac = arg
     print "Searching for Slice Information for mac " + smac
   elif opt in ("-v", "--vlan"):
     svlan = arg
     print "Searching for Slice Information for vlan " + svlan


 config.initialize("/etc/gram/config.json")

 organization = gmoc.Organization( ORGNAME )
 pop = gmoc.POP( POPNAME )
 aggregate = gmoc.Aggregate('urn:publicid:IDN+bbn-cam-ctrl-1+authority+am', type='gram', version='3', pop = pop, operator=organization)
 #print config.stitching_info['aggregate_id']
#import pdb; pdb.set_trace()

 #get vmresources
 vmresources = config.compute_hosts
 stitching_handler = stitching.Stitching()


 resources={}
 for k in vmresources:
  #print k
  #weird - if you don't use str - component_id comes back as type unicode
  component_id = str(config.urn_prefix + "node+" + k)
  #print component_id
  #import pdb; pdb.set_trace()
  resources[k] = gmoc.Resource(component_id, type = 'vmserver', pop = pop, operator = organization)     
 aggregate.resources = resources.values()

 snapshot_dir = config.gram_snapshot_directory + "/" + getpass.getuser()

 allF = []
 files = os.listdir(snapshot_dir)
 for f in files:
  filename = os.path.join(snapshot_dir, f)
  if(os.path.isfile(filename)):
#    print filename
    allF.append(filename)

 if allF:
  nfiles = sorted(allF, key=os.path.getctime)
  oldest = nfiles[0]
  newest = nfiles[-1]

  print "Latest snapshot file: " + newest + "\n"
  myslices = Archiving.read_state(newest, None, stitching_handler)
  sliver = {}

  for i, slice in myslices.iteritems():
   slice_obj = gmoc.Slice(str(slice.getSliceURN()))
   #print "Slice:  "+ str(slice.getSliceURN())
   slivers = slice.getAllSlivers()
   for k, v in slivers.iteritems():
    #print "*********************"
    #import pdb; pdb.set_trace()
    #sliver[v.getSliverURN()] = gmoc.Sliver(str(v.getSliverURN()), v.getExpiration(), v.getOperationalState(), aggregate, v.getUserURN())                                                    
    #sliver[v.getSliverURN()] = gmoc.Sliver(str(v.getSliverURN()), v.getExpiration(), gmoc.SLIVER_STATE_UP, aggregate, gmoc.Contact(str(v.getUserURN())))
    sliver[v.getSliverURN()] = gmoc.Sliver(str(v.getSliverURN()), expires = v.getExpiration(), state = gmoc.SLIVER_STATE_UP, aggregate = aggregate, creator = gmoc.Contact(str(v.getUserURN())))
    sliver[v.getSliverURN()].slice = slice_obj
    sliver[v.getSliverURN()].created = v.getCreation()
    if v.getUUID() is not None:
      sliver[v.getSliverURN()].uuid = uuid.UUID(v.getUUID())

    #print v.getCreation()
    #print v.getExpiration()
    #print v.getSliverURN()
    #print v.getOperationalState()
    #print v.getUserURN()
    #print v.getUUID()
    #print slice.getSliceURN()
    #import pdb; pdb.set_trace()
    #print v

    if isinstance(v, Archiving.VirtualMachine):
      #print "vm"
      #print v.getHost()
      #print v.getExternalIp()
      #why is ExternalIp not set - have to ask Stephen RRH
      #if v.getExternalIp() is not None:
      #  print "IP " + v.getExternalIp()
      #  if sip == str(v.getExternalIp()):
      if sip is not None:
        match = re.search(sip, str(v))
        if match:
          #print "FOUND IP " + match.group()
          print "Diagnostic Information for ip = " + sip + ":"
          printDiagInfo(slice, v)
          found = True
          sliver[v.getSliverURN()].extIP = match.group()
          return


      #else:
      #  print "No external IP "
      #print "v.getHost " + v.getHost()
      #print "v.getSliverURN " + v.getSliverURN()
      if v.getHost() != None and v.getSliverURN() != None:
        gmoc.ResourceMapping(str(v.getUUID()), type = 'vm', resource = resources[v.getHost()], sliver = sliver[v.getSliverURN()])
      #print "*********************"

    elif isinstance(v, Archiving.NetworkLink):
      #print "Link"
      if v.getVLANTag() is not None:
        #print "vlan " + str(v.getVLANTag())
        if svlan == str(v.getVLANTag()):
          print "Diagnostic Information for vlan = " + svlan + ":"
          printDiagInfo(slice, v)
          found = True
          return

        sliver[v.getSliverURN()].vlan = str(v.getVLANTag())
      #else:
      #  print "No VLAN Tag"
      #print "*********************"

    elif isinstance(v, Archiving.NetworkInterface):
      #print "NIC"
      #print "mac " + v.getMACAddress()
      if smac == str(v.getMACAddress()):
        print "Diagnostic Information for mac = " + smac + ":"
        printDiagInfo(slice, v)
        found = True
        return

      sliver[v.getSliverURN()].mac = str(v.getMACAddress())
      if v.getVLANTag() is not None:
        #print "vlan " + str(v.getVLANTag())
        if svlan == str(v.getVLANTag()):
          print "Diagnostic Information for vlan = " + svlan + ":"
          printDiagInfo(slice, v)
          found = True
          return

        sliver[v.getSliverURN()].vlan = str(v.getVLANTag())
      #else:
      #  print "No VLAN Tag"
      #print "*********************"
    else:
      print "Unknown Sliver Type"
      print "*********************"
    
#    print sliver
 # Now actually setup and report stuff
 #client = gmoc.GMOCClient(                                                                         
 #          serviceURL = 'https://gmoc-db.grnoc.iu.edu/',                                          
 #          username = MONUSERNAME,
 #          password = MONPASSWORD,
 #        )

# import pdb; pdb.set_trace()
 if found == False:
   print "\n\n*********************"
   print "PRINTING ALL CURRENT INFORMATION FOR " + time.strftime("%c")
   print pop
   print "*********************"


#if DEBUG:  # assuming you set an optional debugging flag, which is a good idea                    
#  client.debugLevel = gmoc.GMOC_DEBUG_VERBOSE                                                      

# result = client.store(pop)                                                                      
# if result != 0:                                                                                   
#  print "Attempted to submit relational data, but received: %s" % result
#  print "HTTP status code was: %d" % data.resultStatus                                            
#  print "Error message was: %s" % data.errorMessage                     

if __name__ == "__main__":

  if len(sys.argv) > 1:
    if len(sys.argv) <= 3:
      monitor(sys.argv[1:]) 
    else:
      usage()
  else:
  #run as a daemon
    while True:
      monitor('-d') 
      time.sleep(10)
