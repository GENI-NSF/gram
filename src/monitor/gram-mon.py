import open_stack_interface
import Archiving
import config
import gmoc
import os
import getpass
import time

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


def monitor():
 organization = gmoc.Organization( ORGNAME )
 pop = gmoc.POP( POPNAME )
 aggregate = gmoc.Aggregate('urn:publicid:geni:bos:gcf+authority+am', type='gram', version='3', pop = pop, operator=organization)

 #get vmresources
 vmresources = open_stack_interface._getConfigParam('/etc/gram/config.json', 'compute_hosts')

 resources={}
 for k in vmresources:
  print k
  #weird - if you don't use str - component_id comes back as type unicode
  component_id = str(config.urn_prefix + "node+" + k)
  print component_id
  #import pdb; pdb.set_trace()
  resources[k] = gmoc.Resource(component_id, type = 'vmserver', pop = pop, operator = organization)     
 aggregate.resources = resources.values()

 snapshot_dir = config.gram_snapshot_directory + "/" + getpass.getuser()

 allF = []
 files = os.listdir(snapshot_dir)
 for f in files:
  filename = os.path.join(snapshot_dir, f)
  if(os.path.isfile(filename)):
    print filename
    allF.append(filename)

 if allF:
  nfiles = sorted(allF, key=os.path.getctime)
  oldest = nfiles[0]
  newest = nfiles[-1]

  myslices = Archiving.read_slices(newest)
  sliver = {}

  for i, slice in myslices.iteritems():
   gmoc.Slice(str(slice.getSliceURN()))
   slivers = slice.getAllSlivers()
   for k, v in slivers.iteritems():
    print "*********************"
    #import pdb; pdb.set_trace()
    #sliver[v.getSliverURN()] = gmoc.Sliver(str(v.getSliverURN()), v.getExpiration(), v.getOperationalState(), aggregate, v.getUserURN())                                                    
    #sliver[v.getSliverURN()] = gmoc.Sliver(str(v.getSliverURN()), v.getExpiration(), gmoc.SLIVER_STATE_UP, aggregate, gmoc.Contact(str(v.getUserURN())))
    sliver[v.getSliverURN()] = gmoc.Sliver(str(v.getSliverURN()), expires = v.getExpiration(), state = gmoc.SLIVER_STATE_UP, aggregate = aggregate, creator = gmoc.Contact(str(v.getUserURN())))
    print v.getCreation()
    print v.getExpiration()
    print v.getSliverURN()
    print v.getOperationalState()
    print v.getUserURN()
    print v.getUUID()
    print slice.getSliceURN()
    if isinstance(v, Archiving.VirtualMachine):
      print "vm"
      print v.getHost()
      #have a question about the UUID and the slivers class assigned at the end of this function
      gmoc.ResourceMapping(str(v.getUUID()), type = 'vm', resource = resources[v.getHost()], sliver = sliver[v.getSliverURN()])                                                                             
    else:
      print "link"
      print "*********************"



 # Now actually setup and report stuff
 client = gmoc.GMOCClient(                                                                         
           serviceURL = 'https://gmoc-db.grnoc.iu.edu/',                                          
           username = MONUSERNAME,
           password = MONPASSWORD,
         )

 print pop
#if DEBUG:  # assuming you set an optional debugging flag, which is a good idea                    
#  client.debugLevel = gmoc.GMOC_DEBUG_VERBOSE                                                      

# result = client.store(pop)                                                                      
# if result != 0:                                                                                   
#  print "Attempted to submit relational data, but received: %s" % result
#  print "HTTP status code was: %d" % data.resultStatus                                            
#  print "Error message was: %s" % data.errorMessage                     

if __name__ == "__main__":

    while True:
    	monitor() 
        time.sleep(10)
