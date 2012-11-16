# Set of classes of resources (and supporting structures)
# the aggregate can allocate and about which it maintains state

import inspect;

# Helper function for generating field-by-field image 
# for resources
def sliver_list_image(slivers):
   image = ""
   for sliver in slivers:
      image = image + sliver.getComponentID() + " ";
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
   def __init__(self, slice_urn, sa_urn, user_urn, expiration, \
                    tenant_id, router_id, manifest_rspec):
      self._slice_urn = slice_urn
      self._sa_urn = sa_urn
      self._user_urn = user_urn
      self._expiration = expiration
      self._tenant_id = tenant_id
      self._router_id = router_id
      self._manifest_rspec = manifest_rspec

   def __str__(self):
      return resource_image(self, "Slice");

   # Getters

   def getSliceURN(self):  # String Slice URN
       return self._slice_urn

   def getSAURN(self): # String Slice Authority URN
       return self._sa_urn

   def getUserURN(self): # String User URN
       return self._user_urn

   def getExpiration(self): # Date expiration of slice
       return self._expiration

   def getTenantID(self): # OpenStack tenant UUID
       return self._tenant_id

   def getRouterID(self): # UUID of router of slice
       return self._router_id

   # Manifest RSpec returned at time of slice / slivers creation
   def getManifestRSpec(self): 
       return self._manifest_rspec

   # Setters

   def setSliceURN(self, slice_urn):  # String Slice URN
       rself._slice_urn = slice_urn

   def setSAURN(self, sa_urn): # String Slice Authority URN
       self._sa_urn = sa_urn

   def setUserURN(self, user_urn): # String User URN
       self._user_urn = user_urn

   def setExpiration(selfexpiration): # Set expiration of slice
       self._expiration = expiration;

   def setTenantID(self, tenant_id): # OpenStack tenant UUID
       self._tenant_id = tenant_id

   def setRouterID(self, router_id): # UUID of router of slice
       self._router_id = router_id

   # Manifest RSpec returned at time of slice / slivers creation
   def setManifestRSpec(self, manifest_rspec): 
       self._manifest_rspec = manifest_rspec


# Base class for resource slivers
class Sliver():
    def __init__(self, uuid, component_id, slice, expiration):
        self._uuid = uuid;
        self._component_id = component_id;
        self._slice = slice;
        self._expiration = expiration;

    # Getters

    def getUUID(self): # Return OpenStack UUID of resource
        return self._uuid;

    def getComponentID(self): # Return component_id of sliver (sliver_URN)
        return self._component_id;

    def getSlice(self): # Return slice associated with sliver
        return self._slice;

    def getExpiration(self):
        return self._expiration;

    # Setters
    def setUUID(self, uuid): # Return OpenStack UUID of resource
        self._uuid = uuid;

    # Return component_id of sliver (sliver_URN)
    def setComponentID(self, component_id): 
        self._component_id = component_id;

    def setSlice(self, slice): # Return slice associated with sliver
        self._slice = slice;

    def setExpiration(selfexpiration):
        self._expiration = expiration


# A virtual machine resource
# Note, we don't support bare-metal machines (yet).
class VirtualMachine(Sliver): # 
    def __init__(self, uuid, component_id, slice, expiration, \
                     control_net_addr, node_name, installs, executes, \
                     network_interfaces, authorized_user_urns, \
                     allocation_state, operational_state, flavor, \
                     image_id):
        Sliver.__init__(self, uuid, component_id, slice, expiration);
        self._control_net_addr = control_net_addr
        self._node_name = node_name
        self._installs = installs
        self._executes = executes
        self._network_interfaces = network_interfaces
        self._authorized_user_urns = authorized_user_urns
        self._allocation_state = allocation_state
        self._operational_state = operational_state
        self._flavor = flavor
        self._image_id = image_id


    def __str__(self):
       return resource_image(self, "VM");

    # Getters

    def getControlNetAddr(self): # IP Address of controller
        return self._control_net_addr;

    def getNodeName(self): # User supplied name of node
        return self._node_name;

    def getInstalls(self): # List of files to install on VM
        return self._installs;

    def getExecutes(self) : # List of commands to execute on VM startup
        return self._executes;

    def getNetworkInterfaces(self): # List of network interfaces
        return self._network_interfaces;

    def getAuthorizedUserURNs(self): # String URN of authorized users
        return self._authorized_usr_urns;

    def getImageID(self): # OpenStack UUID of image
        return self._image_id

    def getAllocationState(self): # int allocation state of sliver (allocated, procured, freed, etc).
        return self._allocation_state

    def getOperationalState(self): # int operational state of sliver (initializing, operational, destroying, etc.)
        return self._operational_state

    def getFlavor(self): # int flavor type
        return self._flavor

    # Setters

    def setControlNetAddr(self, control_net_addr): # IP Address of controller
        self._control_net_addr = control_net_addr;

    def setNodeName(self, node_name): # User supplied name of node
        self._node_name = node_name;

    def setInstalls(self, installs): # List of files to install on VM
        self._installs = installs;

    # List of commands to execute on VM startup
    def setExecutes(self, executes) : 
        self._executes = executes;

    # String URN of authorized users
    def setAuthorizedUserURNs(self, authorized_usr_urns): 
        self._authorized_usr_urns = authorized_usr_urns;

    def setImageID(self, image_id): # OpenStack UUID of image
        self._image_id = image_id

    def setFlavor(self, flavor): # int flavor type
        self._flavor = flavor

    def setAllocationState(selfallocation_state):
        self._allocation_state = allocation_state

    def setOperationalState(selfoperational_state):
        self._operational_state = operational_state

    # NetworkInterfaces might not be defined at instantiation time
    # Since their constructors reference one another
    def setNetworkInterfaces(self, network_interfaces): 
        self._network_interfaces = network_interfaces;


# A NIC (Network Interface Card) resource
class NetworkInterface(Sliver):  # Was: NIC
     def __init__(self, uuid, component_id, slice, expiration, \
                      name, device_number, mac_address, ip_address, \
                      host, virtual_eth_name, link):
         Sliver.__init__(self, uuid, component_id, slice, expiration);
         self._name = name
         self._device_number = device_number
         self._mac_address = mac_address
         self._ip_address = ip_address
         self._host = host
         self._virtual_eth_name = virtual_eth_name
         self._link = link

     def __str__(self):
        return resource_image(self, "NIC");

     # Getters

     def getName(self): # string user provided name of interface
         return self._name

     def getDeviceNumber(self): # int number of device (2 = eth2, etc.)
         return self._device_number

     def getMACAddress(self): # string MAC address of NIC
         return self._mac_address

     def getIPAddress(self): # string IP address of NIC
         return self._ip_address

     def getHost(self): # Sliver (VM host) associated with NIC
         return self._host

     # string name corresponding to VETH in host O/S
     def getVirtualEthName(self): 
         return self._virtual_eth_name

     def getLink(self): # NetworkLink associated with NIC
         return self._link

     # Setters

     def setName(self, name): # string user provided name of interface
         self._name = name

     # int number of device (2 = eth2, etc.)
     def setDeviceNumber(self, device_number): 
         self._device_number = device_number

     def setMACAddress(self, mac_address): # string MAC address of NIC
         self._mac_address = mac_address

     def setIPAddress(self, ip_address): # string IP address of NIC
         self._ip_address = ip_address

     # string name corresponding to VETH in host O/S
     def setVirtualEthName(self, virtual_eth_name): 
         self._virtual_eth_name = virtual_eth_name

     # Link might not be defined at instantiation time, since
     # These classes refer to one another
     def setLink(self, link) : # Set NetworkLink associated with NIC
        self._link = link;

     def setHost(self, host): # Set VirtualMachine host for NIC
        self._host = host;
 

# A Network Link resource
class NetworkLink(Sliver): # was Link
     def __init__(self, uuid, component_id, slice, expiration, \
                      name, subnet, endpoints, \
                      network_id, vlan_tag):
         Sliver.__init__(self, uuid, component_id, slice, expiration);
         self._name = name
         self._subnet = subnet
         self._endpoints = endpoints
         self._network_id = network_id
         self._vlan_tag = vlan_tag

     def __str__(self):
        return resource_image(self, "Link");

     # Getters

     def getName(self): # string user provided name of link
         return self._name

     def getSubnet(self): # int (10.0.x.0/24)
         return self._subnet

     def getEndpoints(self): # List of NetworkInterfaces
         return self._endpoints

     def getNetworkID(self): # OpenStack UUID of network of link
         return self._network_id

     def getVLANTag(self): # Return vlan tag of traffic on this link
         return self._vlan_tag

     # Setters

     def setName(self, name): # string user provided name of link
         self._name = name

     def setSubnet(self, subnet): # int (10.0.x.0/24)
         self._subnet = subnet

     def setNetworkID(self, network_id): # OpenStack UUID of network of link
         self._network_id = network_id

     def setVLANTag(self, vlan_tag): # Return vlan tag of traffic on this link
         self._vlan_tag = vlan_tag

     # NetworkInterfaces might not exist at construction time, since
     # Constructors reference one another
     def setEndpoints(self, endpoints):
        self._endpoints = endpoints;

 
 

