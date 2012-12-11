# Set of classes of resources (and supporting structures)
# the aggregate can allocate and about which it maintains state

import inspect
import uuid

import config

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
            value_image = value.getComponentID()
         if isinstance(obj, VirtualMachine) and name == "_network_interfaces":
            value_image = sliver_list_image(obj._network_interfaces)
         if isinstance(obj, NetworkLink) and name == "_endpoints":
            value_image = sliver_list_image(obj._endpoints)
         members_image = members_image + " " + name + ":" + value_image;
   return "#<" + label + " " + members_image + ">";



# A slice that has been allocated.
class Slice:
   def __init__(self, slice_urn) :
      self._slice_urn = slice_urn
      self._tenant_name = None    # OpenStack tenant name
      self._tenant_uuid = None    # OpenStack tenant uuid
      self._tenant_admin_name = None # Admin user for this tenant
      self._tenant_admin_pwd = None  # Password for the admin user
      self._tenant_admin_uuid = None # UUID of the admin user
      self._router_name = None    # Name of router for this tenant (slice)
      self._router_uuid = None    # UUID of router for this tenant (slice)
      self._control_net_info = None  # name, uuid, ip addr, etc for control net
      self._user_urn = None
      self._expiration = None
      self._request_rspec = None
      self._manifest_rspec = None
      self._slivers = {} # Map of sliverURNs to slivers
      self._VMs = []    # VirtualMachines that belong to this slice
      self._NICs = []   # NetworkInterfaces that belong to this slice
      self._links = []  # NetworkLinks that belong to this slice
      self._last_subnet_assigned = 2 # If value is x then the last subnet
                                     # address assinged to a link in the slice
                                     # was 10.0.x.0/24.  Starts with 2 since
                                     # 10.0.1.0/24 is for the control network
                                     # and 10.0.2.0/24 is often used by the
                                     # underlying virtualization technology
   def __str__(self):
      return resource_image(self, "Slice");
   
   # Called by slivers to add themselves to the slice
   def addSliver(self, sliver) :
      sliver_urn = sliver.getSliverURN()
      if sliver_urn != None :
         self._slivers[sliver_urn] = sliver
      else :
         config.log.error('Adding sliver to slice; sliver does not have a URN')
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

   def setControlNetInfo(self, info) :
      self._control_net_info = info

   def getControlNetInfo(self) :
      return self._control_net_info

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
      return self._slivers

   def generateSubnetAddress(self) :
      self._last_subnet_assigned += 1
      #### START TEMP CODE.  REMOVE WHEN WE HAVE NAMESPACES WORKING
      subnet_num_file = open('/home/vthomas/GRAM-next-subnet.txt', 'r+')
      last_subnet_assigned = int(subnet_num_file.readline().rstrip())
      subnet_num_file.close()
      subnet_num_file = open('/home/vthomas/GRAM-next-subnet.txt', 'w')
      last_subnet_assigned += 1
      if last_subnet_assigned == 256 :
         last_subnet_assigned = 19
      subnet_num_file.write(str(last_subnet_assigned))
      subnet_num_file.close()
      return '10.0.%s.0/24' % last_subnet_assigned
      #### END TEMP CODE
      return '10.0.%s.0/24' % self._last_subnet_assigned

   def generateControlNetAddress(self) :
      #### START TEMP CODE.  REMOVE WHEN WE HAVE NAMESPACES WORKING
      subnet_num_file = open('/home/vthomas/GRAM-next-subnet.txt', 'r+')
      last_subnet_assigned = int(subnet_num_file.readline().rstrip())
      subnet_num_file.close()
      subnet_num_file = open('/home/vthomas/GRAM-next-subnet.txt', 'w')
      last_subnet_assigned += 1
      if last_subnet_assigned == 256 :
         last_subnet_assigned = 19
      subnet_num_file.write(str(last_subnet_assigned))
      subnet_num_file.close()
      return '10.10.%s.0/24' % last_subnet_assigned 
      #### END TEMP CODE
     
   def setControlNetAddress(self, addr) :
      self._control_net_addr = addr

   def getControlNetAddress(self) :
      return self._control_net_addr 

   def getSliceURN(self):  # String Slice URN
      return self._slice_urn

   def getUserURN(self): # String User URN
      return self._user_urn

   def getExpiration(self): # Date expiration of slice
      return self._expiration

   # Manifest RSpec returned at time of slice / slivers creation
   def getManifestRSpec(self): 
      return self._manifest_rspec

   def setExpiration(selfexpiration): # Set expiration of slice
      self._expiration = expiration;

   def setRequestRspec(self, rspec) :
      self._request_rspec = rspec
      
   def getRequestRspec(self) :
      return self._request_rspec
      
      

# Base class for resource slivers
class Sliver():
   def __init__(self, my_slice) :
      self._sliver_urn = self._generateURN()    # URN of this sliver
      self._uuid = None     # OpenStack UUID of resource
      self._slice = my_slice # Slice associated with sliver
      self._expiration = None # Sliver expiration time
      self._name = None    # Experimenter specified name of the sliver
      self._allocation_state = config.allocated  # API v3 allocation state
      self._operational_state = config.pending_allocation  # Operational state
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
   _next_octet = 100  # Last octet of an ip address.  Used when assigning
                      # ip addresses to the interfaces on the VM
   def __init__(self, my_slice) :
      self._control_net_addr = None  # IP address of VM on the control net
      self._installs = []    # Items to be installed on the VM on startup
      self._executes = []    # Scripts to be extecuted on the VM on startup
      self._network_interfaces = []   # Associated network interfaces
      self._ip_last_octet = VirtualMachine._next_octet # All IP addresses
                     # assigned to this VM will be of the form 10.0.x.last_octet
      VirtualMachine._next_octet += 1
      self._authorized_user_urns = None
      self._flavor = config.default_VM_flavor
      self._os_image = config.default_OS_image
      Sliver.__init__(self, my_slice)

   def __str__(self):
      return resource_image(self, "VM") 

   def addNetworkInterface(self, netInterface) :
      self._network_interfaces.append(netInterface)

   def setControlNetAddr(self, ip_addr) : 
      self._control_net_addr = ip_addr

   def getControlNetAddr(self): 
      return self._control_net_addr 

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

   def getVMFlavor(self) :
      return self._flavor

   def addInstallItem(self, source, destination, file_type) :
      self._installs.append(_InstallItem(source, destination, file_type))

   def addExecuteItem(self, command, shell) :
      self._executes.append(_ExecuteItem(command, shell))


# A NIC (Network Interface Card) resource
class NetworkInterface(Sliver):  # Was: NIC
     def __init__(self, my_slice, myVM) :
         self._device_number = None
         self._mac_address = None  # string MAC address of NIC
         self._ip_address = None   # string IP address of NIC
         self._vm = myVM    # VirtualMachine associated with this NIC
         self._link = None  # NetworkLink associated with NIC
         Sliver.__init__(self, my_slice)

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

     def getLink(self): # NetworkLink associated with NIC
         return self._link

     def setLink(self, link) :
        self._link = link;

     def setHost(self, host): # Set VirtualMachine host for NIC
        self._host = host;
 

# A Network Link resource
class NetworkLink(Sliver): # was Link
     def __init__(self, my_slice) :
        self._subnet = None     # IP subnet: 10.0.x.0/24
        self._endpoints = []    # List of NetworkInterfaces attached to link
        self._network_uuid = None # quantum UUID of the link's network 
        self._subnet_uuid = None  # quantum UUID of the link's subnet 
        self._vlan_tag = None
        Sliver.__init__(self, my_slice);

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
     
     def getVLANTag(self): # Return vlan tag of traffic on this link
         return self._vlan_tag
