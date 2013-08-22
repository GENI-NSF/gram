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

# Set of classes of resources (and supporting structures)
# the aggregate can allocate and about which it maintains state

import datetime
import dateutil.parser
import inspect
import uuid
import threading
import os

import config
import constants

# Helper function for generating field-by-field image 
# for resources
def sliver_list_image(slivers):
   image = ""
   for sliver in slivers:
      image = image + sliver.getUUID() + " ";
   return "[" + image + "]"

def resource_image(obj, label):
   members = inspect.getmembers(obj);
   members_image = "";
   for m in members:
      name = m[0]
      value = m[1]
      if value is not None and not callable(value) and not name == "__module__":
         value_image = str(value)
         # Handle special cases to print URN instead of resource sub-object
         if isinstance(value, Slice):
            value_image = value.getSliceURN()
         if isinstance(value, Sliver):
            value_image = value.getUUID()
         if isinstance(obj, VirtualMachine) and name == "_network_interfaces":
            value_image = sliver_list_image(obj._network_interfaces)
         if isinstance(obj, NetworkLink) and name == "_endpoints":
            value_image = sliver_list_image(obj._endpoints)
         members_image = members_image + " " + name + ":" + value_image;
   return "#<" + label + " " + members_image + ">";


# Holds information about the GRAM management network (used for aggregate
# control plane traffic).  E.g. ssh connections to the VMs
class GramManagementNetwork :
   _mgmt_net_uuid = None

   @staticmethod
   def set_mgmt_net_uuid(net_uuid) :
      GramManagementNetwork._mgmt_net_uuid = net_uuid

   @staticmethod
   def get_mgmt_net_uuid() :
      return GramManagementNetwork._mgmt_net_uuid


# A slice that has been allocated.
class Slice:
   def __init__(self, slice_urn) :
      self._slice_urn = slice_urn
      self._slice_lock = threading.RLock() # Control access to Slice and Slivers
      self._tenant_name = None    # OpenStack tenant name
      self._tenant_uuid = None    # OpenStack tenant uuid
      self._tenant_admin_name = None # Admin user for this tenant
      self._tenant_admin_pwd = None  # Password for the admin user
      self._tenant_admin_uuid = None # UUID of the admin user
      self._tenant_security_grp = None # Security group for tenant (slice)
      self._router_name = None    # Name of router for this tenant (slice)
      self._router_uuid = None    # UUID of router for this tenant (slice)
      self._user_urn = None
      self._expiration = None
      self._request_rspec = None  # Most recent request rspec (may be > 1)
      self._manifest_rspec = None   ## TEMP: We should not be saving manifests
      self._slivers = {} # Map of sliverURNs to slivers
      self._VMs = []    # VirtualMachines that belong to this slice
      self._NICs = []   # NetworkInterfaces that belong to this slice
      self._links = []  # NetworkLinks that belong to this slice
      self._last_subnet_assigned = 2 # If value is x then the last subnet
                                     # address assinged to a link in the slice
                                     # was 10.0.x.0/24.  Starts with 2 since
                                     # 10.0.1.0/24 is for the management network
                                     # and 10.0.2.0/24 is often used by the
                                     # underlying virtualization technology
      self._next_vm_num = 99  # All VMs in the slice are assigned numbers 
                              #  starting with 100.  This number is used as the
                              #  last octet for all IP addresses assigned to 
                              #  that VM.
      self._controller_url = None    # Provided experimenter controller, if any

   def __str__(self):
      return resource_image(self, "Slice");
   
   def getLock(self) :
      return self._slice_lock

   # Called by slivers to add themselves to the slice
   def addSliver(self, sliver) :
      sliver_urn = sliver.getSliverURN()
      if sliver_urn != None :
         self._slivers[sliver_urn] = sliver
      else :
         config.logger.error('Adding sliver to slice; sliver does not have a URN')

      if sliver.__class__.__name__ == 'VirtualMachine' :
         self._VMs.append(sliver)
         return True
      elif sliver.__class__.__name__ == 'NetworkInterface' :
         self._NICs.append(sliver)
         return True
      elif sliver.__class__.__name__ == 'NetworkLink' :
         self._links.append(sliver)
         return True
      else :
         config.logger.error('Unknown sliver type')
         return False

   def removeSliver(self, sliver) :
      sliver_urn = sliver.getSliverURN()
      
      # Remove sliver from list of slivers
      if sliver_urn in self._slivers :
         del self._slivers[sliver_urn]

      # Remove sliver from appropriate list based on sliver type
      if sliver.__class__.__name__ == 'VirtualMachine' :
         # First remove from the slice all NICs associated with this VM
         for nic in sliver.getNetworkInterfaces() :
            self.removeSliver(nic)
         self._VMs.remove(sliver)
      elif sliver.__class__.__name__ == 'NetworkInterface' :
         self._NICs.remove(sliver)
      elif sliver.__class__.__name__ == 'NetworkLink' :
         self._links.remove(sliver)
         
   def setTenantUUID(self, tenant_id ): 
      self._tenant_uuid = tenant_id

   def getTenantUUID(self): 
      return self._tenant_uuid

   def setTenantName(self, tenant_name) :
      self._tenant_name = tenant_name

   def getTenantName(self) :
      return self._tenant_name
   
   def setTenantAdminInfo(self, name, password, uuid) :
      self._tenant_admin_name = name
      self._tenant_admin_pwd = password
      self._tenant_admin_uuid = uuid

   def getTenantAdminInfo(self) :
      return self._tenant_admin_name, self._tenant_admin_pwd, \
          self._tenant_admin_uuid

   def setSecurityGroup(self, sec_grp_name) :
      self._tenant_security_grp = sec_grp_name

   def getSecurityGroup(self) :
      return self._tenant_security_grp 

   def setTenantRouterName(self, name) :
      self._router_name = name

   def getTenantRouterName(self) :
      return self._router_name

   def setTenantRouterUUID(self, uuid) :
      self._router_uuid = uuid

   def getTenantRouterUUID(self) :
      return self._router_uuid

   def getNetworkInterfaceByName(self, name) :
      for i in range(len(self._NICs)) :
         if self._NICs[i].getName() == name :
            return self._NICs[i]
      return None

   def getNetworkLinks(self) :
      return self._links

   def getVMs(self) :
      return self._VMs

   def getSlivers(self) :
      """
          Return a list of VM and link slivers.  These are the only slivers
          relevant to experimenters.  For all sliver objects associated with
          this slice, use getAllSlivers().
      """
      slivers = dict()
      for vm in self._VMs :
         slivers[vm.getSliverURN()] = vm
      for link in self._links :
         slivers[link.getSliverURN()] = link
      return slivers

   def getAllSlivers(self) :
      """
          Return a list of all sliver objects associated with this slice.  For
          a list of slivers relevant to experiemnters (VM and network link 
          slivers), use getSlivers().
      """
      return self._slivers


   def generateSubnetAddress(self) :
      self._last_subnet_assigned += 1

      # can kill temo code if there is namespace
      #### START TEMP CODE.  REMOVE WHEN WE HAVE NAMESPACES WORKING
      if not os.path.isfile(config.subnet_numfile) :
         # The file with the subnet numbers does not exist; create it
         subnet_num_file = open(config.subnet_numfile, 'w')
         subnet_num_file.write(str(19)) # start with subnet 19 -- somewhat
                                        # arbitrary.  19 seems to be safe
         subnet_num_file.close()
            
      # Read from file the number of the last subnet assigned
      subnet_num_file = open(config.subnet_numfile, 'r')
      last_subnet_assigned = int(subnet_num_file.readline().rstrip())
      subnet_num_file.close()

      # Increment the number in the file by 1.  Roll back to 19 if count
      # is at 256
      subnet_num_file = open(config.subnet_numfile, 'w')
      last_subnet_assigned += 1
      if last_subnet_assigned == 256 :
         last_subnet_assigned = 19
      subnet_num_file.write(str(last_subnet_assigned))
      subnet_num_file.close()
      return '10.0.%s.0/24' % last_subnet_assigned
      #### END TEMP CODE
      return '10.0.%s.0/24' % self._last_subnet_assigned

   def getVMNumber(self) :
      self._next_vm_num += 1
      return self._next_vm_num
      
   def getSliceURN(self):  # String Slice URN
      return self._slice_urn

   def getUserURN(self): # String User URN
      return self._user_urn

   def setUserURN(self, user_urn):
      self._user_urn = user_urn

   def getExpiration(self): # Date expiration of slice
      return self._expiration

   def setManifestRspec(self, manifest) :
      self._manifest_rspec = manifest

   def getManifestRspec(self) : 
      return self._manifest_rspec

   def setExpiration(self, expiration): # Set expiration of slice
      self._expiration = expiration;

   def setRequestRspec(self, rspec) :
      self._request_rspec = rspec
      
   def getRequestRspec(self) :
      return self._request_rspec
      
   def setControllerURL(self, controller_url):
      self._controller_url = controller_url

   def getControllerURL(self):
      return self._controller_url
      

# Base class for resource slivers
class Sliver():
   def __init__(self, my_slice, uuid=None) :
      self._slice = my_slice # Slice associated with sliver
      self._sliver_urn = self._generateURN()    # URN of this sliver
      self._uuid = uuid     # OpenStack UUID of resource
      self._expiration = None # Sliver expiration time
      self._name = None    # Experimenter specified name of the sliver
      self._request_rspec = None # Rspec provided at allocation time
      self._manifest_rspec = None # Rspec of current resource state
      self._allocation_state = constants.allocated  # API v3 allocation state
      self._operational_state = constants.notready  # Operational state
      self._user_urn = None
      my_slice.addSliver(self)  # Add this sliver to the list of slivers owned
                                # by the slice.  sliver_urn must be set.

   # When a sliver is created it gets a sliver URN.
   def _generateURN(self) :
      uuid_suffix = str(uuid.uuid4())
      if self.__class__.__name__ == 'VirtualMachine' :
         sliver_urn = config.vm_urn_prefix + uuid_suffix
      elif self.__class__.__name__ == 'NetworkInterface' :
         sliver_urn = config.interface_urn_prefix + uuid_suffix
      elif self.__class__.__name__ == 'NetworkLink' :
         sliver_urn = config.link_urn_prefix + uuid_suffix
      else :
         config.logger.error('Unknown sliver type.  Cannot set URN')
      return sliver_urn
      
   def setName(self, name) :
      self._name = name

   def getName(self) :
      return self._name

   def setUUID(self, uuid) :
      self._uuid = uuid

   def getUUID(self) : 
      return self._uuid

   def getSliverURN(self): 
      return self._sliver_urn

   def getSlice(self): 
      return self._slice;

   def getExpiration(self):
      return self._expiration;

   def setExpiration(self, expiration):
      self._expiration = expiration

   def setAllocationState(self, state) :
      self._allocation_state = state

   def getAllocationState(self) :
      return self._allocation_state 

   def setOperationalState(self, state) :
      self._operational_state = state
      
   def getOperationalState(self) :
      return self._operational_state 

   def getUserURN(self): # String User URN
      return self._user_urn

   def setUserURN(self, user_urn):
      self._user_urn = user_urn

   def setRequestRspec(self, rspec) :
      self._request_rspec = rspec
      
   def getRequestRspec(self) :
      return self._request_rspec
      
   def setManifestRspec(self, rspec) :
      self._manifest_rspec = rspec
      
   def getManifestRspec(self) :
      return self._manifest_rspec
      
   def status(self, geni_error=''):
        """Returns a status dict for this sliver. Used in numerous        
           return values for AM API v3 calls.                  
        """
        expire_string = "None"
        if self.getExpiration() :
           expire_with_tz = \
               self.getExpiration().replace(tzinfo=dateutil.tz.tzutc())
           expire_string = expire_with_tz.isoformat()
           return dict(geni_sliver_urn = self.getSliverURN(),
                       geni_expires = expire_string,
                       geni_allocation_status = self.getAllocationState(),
                       geni_operational_status = self.getOperationalState(),
                       geni_error = geni_error)
           

class _InstallItem :
   """
       The VirtualMachine class maintains a list of files to be installed
       when the VM starts up.  Items in this list belong to this class.
   """
   def __init__(self, source, dest, file_type) :
      self.source_url = source # From where to get the file to be installed
      self.destination = dest  # Location in VM's file system file should go
      self.file_type = file_type  # File type.  E.g. tar.gz.


class _ExecuteItem :
   """
        The VirtualMachine class  maintains a list of commands to be executed 
        when the VM starts up.  Items in this list belong this class.
    """
   def __init__(self, exec_command, exec_shell) :
      self.command = exec_command  # Command to be executed at VM startup
      self.shell = exec_shell      # Shell used to execute command

# A virtual machine resource
# Note, we don't support bare-metal machines (yet).
class VirtualMachine(Sliver): # 
   def __init__(self, my_slice, uuid=None) :
      self._mgmt_net_addr = None  # IP address of VM on the management net
      self._installs = []    # Items to be installed on the VM on startup
      self._executes = []    # Scripts to be extecuted on the VM on startup
      self._network_interfaces = []   # Associated network interfaces
      self._ip_last_octet = my_slice.getVMNumber() # All IP addresses
                     # assigned to this VM will be of the form x.x.x.last_octet
      self._flavor = config.default_VM_flavor
      self._os_image = config.default_OS_image
      self._os_type = config.default_OS_type
      self._os_version = config.default_OS_version
      self._host = None # name of compute node on which VM resides
      self._authorized_users =  None # List of User names with accts on the VM
      self._ssh_proxy_login_port = None # Port number assigned for remote 
                                        # SSH proxy login
      Sliver.__init__(self, my_slice, uuid)

   def __str__(self):
      return resource_image(self, "VM") 

   def addNetworkInterface(self, netInterface) :
      self._network_interfaces.append(netInterface)

   def setMgmtNetAddr(self, ip_addr) : 
      self._mgmt_net_addr = ip_addr

   def getMgmtNetAddr(self): 
      return self._mgmt_net_addr 

   def getInstalls(self): # List of files to install on VM
      return self._installs 

   def getExecutes(self) : # List of commands to execute on VM startup
      return self._executes 

   def getNetworkInterfaces(self) :
      return self._network_interfaces 

   def getLastOctet(self) :
      return str(self._ip_last_octet)

   def getOSImageName(self) :
      return self._os_image

   def setOSImageName(self, os_image) :
      self._os_image = os_image

   def getOSType(self) :
      return self._os_type

   def setOSType(self, os_type) :
      self._os_type = os_type

   def getOSVersion(self) :
      return self._os_version

   def setOSVersion(self, os_version) :
      self._os_version = os_version

   def getVMFlavor(self) :
      return self._flavor

   def setVMFlavor(self, flavour) : # Set VirtualMachine flavor
      self._flavor = flavour

   def addInstallItem(self, source, destination, file_type) :
      self._installs.append(_InstallItem(source, destination, file_type))

   def addExecuteItem(self, command, shell) :
      self._executes.append(_ExecuteItem(command, shell))

   def getHost(self):
      return self._host

   def setHost(self, host): # Name of compute node on which VM resides
      self._host = host;

   def setAuthorizedUsers(self, user_list) :
      self._authorized_users = user_list

   def getAuthorizedUsers(self) :
      return self._authorized_users 

   def setSSHProxyLoginPort(self, port_number) :
      self._ssh_proxy_login_port = port_number

   def getSSHProxyLoginPort(self) :
      return self._ssh_proxy_login_port
 

# A NIC (Network Interface Card) resource
class NetworkInterface(Sliver):  
     def __init__(self, my_slice, myVM, uuid=None) :
         self._device_number = None
         self._mac_address = None  # string MAC address of NIC
         self._ip_address = None   # string IP address of NIC
         self._vm = myVM    # VirtualMachine associated with this NIC
         self._link = None  # NetworkLink associated with NIC
         self._vlan_tag = None
         self._enabled = False # False => NIC not connected to provisioned link
         Sliver.__init__(self, my_slice, uuid)

     def __str__(self):
        return resource_image(self, "NIC");

     def getDeviceNumber(self): # int number of device (2 = eth2, etc.)
        return self._device_number

     def setMACAddress(self, mac_addr): 
        self._mac_address = mac_addr

     def getMACAddress(self): 
        return self._mac_address

     def setIPAddress(self, ip_addr): 
        self._ip_address = ip_addr

     def getIPAddress(self): 
        return self._ip_address

     def getVM(self): 
        return self._vm

     def setVM(self, vm):
        self._vm = vm

     def getLink(self): # NetworkLink associated with NIC
        return self._link

     def setLink(self, link) :
        self._link = link;

     def enable(self) :
        self._enabled = True
        
     def isEnabled(self) :
        return self._enabled

     def getVLANTag(self): # Return vlan tag of traffic on this interface
        return self._vlan_tag

     def setVLANTag(self, vlan_tag): # Set VLAN tag of traffic on this interface
        self._vlan_tag = vlan_tag


# A Network Link resource
class NetworkLink(Sliver): # was Link
     def __init__(self, my_slice, uuid=None) :
        self._subnet = None     # IP subnet: 10.0.x.0/24
        self._endpoints = []    # List of NetworkInterfaces attached to link
        self._network_uuid = None # quantum UUID of the link's network 
        self._subnet_uuid = None  # quantum UUID of the link's subnet 
        self._vlan_tag = None
        Sliver.__init__(self, my_slice, uuid);

     def __str__(self):
        return resource_image(self, "Link")

     def setSubnet(self, subnetAddr) :
        self._subnet = subnetAddr

     def getSubnet(self) :
        return self._subnet

     def addEndpoint(self, end_point) :
        self._endpoints.append(end_point)

     def getEndpoints(self) : 
        return self._endpoints

     def setNetworkUUID(self, uuid): 
        self._network_uuid = uuid

     def getNetworkUUID(self) : 
        return self._network_uuid

     def setSubnetUUID(self, uuid) :
        self._subnet_uuid = uuid

     def getSubnetUUID(self) :
        return self._subnet_uuid

     def setVLANTag(self, vlan_tag) :
        self._vlan_tag = vlan_tag

     def getVLANTag(self) :
        return self._vlan_tag
     
