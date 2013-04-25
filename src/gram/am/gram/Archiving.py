# Routines and helper classes for saving/restoring AggregateState
# to/from files using JSON

import datetime
import time
import json
import pdb
from resources import Slice, VirtualMachine, NetworkLink, NetworkInterface
#from AggregateState import AggregateState
#from AllocationManager import AllocationManager

class GramJSONEncoder(json.JSONEncoder):

    def default(self, o):

#        print "In Default " + str(o)
        # if isinstance(o, AggregateState):
        #     return {
        #         "__type__":"AggregateState",
        #         "sequence_number": o._sequence_number,
        #         "archive_directory": o._archive_directory,
        #         "public_vlan_tags": o._public_vlan_tags,
        #         "vlan_manager": o._vlan_tag_manager,
        #         "public_ip_addresses": o._public_ip_addresses,
        #         "ip_address_manager": o._ip_address_manager,
        #         "flavor_capacities": o._flavor_capacities,
        #         "flavor_manager": o._flavor_manager,
        #         "flavor_allocations": o._flavor_allocations,
        #         "parameters": o._parameters,
        #         "slivers_by_urn": o._slivers_by_urn
        #         }
                
        # if isinstance(o, AllocationManager):
        #     return {
        #         "__type__":"AllocationManager",
        #         "max_slivers": o._max_slivers,
        #         "resources": o._resources
        #         }

        if isinstance(o, Slice):
            tenant_admin_name, tenant_admin_pwd, tenant_admin_uuid = \
                o.getTenantAdminInfo()
            expiration_time = time.mktime(o.getExpiration().timetuple())
            return {
                "__type__":"Slice", 
                "tenant_uuid":o.getTenantUUID(),
                "tenant_name":o.getTenantName(),
                "tenant_admin_name":tenant_admin_name,
                "tenant_admin_pwd":tenant_admin_pwd,
                "tenant_admin_uuid":tenant_admin_uuid,
                "control_net_info":o.getControlNetInfo(),
                "tenant_router_name":o.getTenantRouterName(),
                "tenant_router_uuid":o.getTenantRouterUUID(),
#                "control_net_address":o.getControlNetAddress(),
                "slice_urn":o.getSliceURN(),
                "user_urn":o.getUserURN(),
                "expiration":expiration_time,
                "manifest_rspec":o.getManifestRspec(),
                "request_rspec":o.getRequestRspec(),
                "last_subnet_assigned":o._last_subnet_assigned,
                "next_vm_num":o._next_vm_num,
                "controller_url":o.getControllerURL(),
                "slivers":[sliver.getSliverURN() for sliver in o.getSlivers().values()]
                  
                }

        if isinstance(o, VirtualMachine):
            expiration_time = time.mktime(o.getExpiration().timetuple())
            return {"__type__":"VirtualMachine",
                    "name":o.getName(),
                    "uuid":o.getUUID(),
                    "sliver_urn":o.getSliverURN(),
                    "slice":o.getSlice().getTenantUUID(),
                    "expiration":expiration_time,
                    "allocation_state":o.getAllocationState(),
                    "operational_state":o.getOperationalState(),
                    "control_net_addr":o.getControlNetAddr(),
                    "installs":o.getInstalls(),
                    "executes":o.getExecutes(),
                    "network_interfaces":[nic.getSliverURN() for nic in o.getNetworkInterfaces()],
                    "last_octet":o.getLastOctet(),
                    "os_image":o.getOSImageName(),
                    "os_type":o.getOSType(),
                    "os_version":o.getOSVersion(),
                    "vm_flavor":o.getVMFlavor(),
                    "host":o.getHost()
                    }
        

        if isinstance(o, NetworkInterface):
            expiration_time = time.mktime(o.getExpiration().timetuple())
            vm_urn = None
            if o.getVM(): vm_urn = o.getVM().getSliverURN();
            link_urn = None
            if o.getLink(): link_urn = o.getLink().getSliverURN()
            return {"__type__":"NetworkInterface",
                    "name":o.getName(),
                    "uuid":o.getUUID(),
                    "sliver_urn":o.getSliverURN(),
                    "slice":o.getSlice().getTenantUUID(),
                    "expiration":expiration_time,
                    "allocation_state":o.getAllocationState(),
                    "operational_state":o.getOperationalState(),
                    "device_number":o.getDeviceNumber(),
                    "mac_address":o.getMACAddress(),
                    "ip_address":o.getIPAddress(),
                    "virtual_machine":vm_urn,
                    "link":link_urn,
                    "vlan_tag":o.getVLANTag()
                    }


        if isinstance(o, NetworkLink):
            expiration_time = time.mktime(o.getExpiration().timetuple())
            return {"__type__":"NetworkLink",
                    "name":o.getName(),
                    "uuid":o.getUUID(),
                    "sliver_urn":o.getSliverURN(),
                    "slice":o.getSlice().getTenantUUID(),
                    "expiration":expiration_time,
                    "allocation_state":o.getAllocationState(),
                    "operational_state":o.getOperationalState(),
                    "subnet":o.getSubnet(),
                    "endpoints":[ep.getSliverURN() for ep in o.getEndpoints()],
                    'vlan_tag':o.getVLANTag(),
                    "network_uuid":o.getNetworkUUID(),
                    "subnet_uuid":o.getSubnetUUID()
                    }



# THis should create a JSON structure which is a list
# of the JSON encoding of all slices and then all slivers
def write_slices(filename, slices):
#    print "WS.CALL " + str(slices) + " " + filename
    file = open(filename, "w")
    objects = []
    for slice in slices.values(): 
        objects.append(slice)
    for slice in slices.values(): 
        for sliver in slice.getSlivers().values():
            objects.append(sliver)
    data = GramJSONEncoder().encode(objects)
    file.write(data)
    file.close();

# Decode JSON representation of list of slices and associated slivers
# Comes as a list of slices and slivers
# As we parse, we keep track of different relationships which
# Can then be restored once we have all the objects by UUID
class GramJSONDecoder:
    def __init__(self):
        self._slices_by_tenant_uuid = {} 

        self._slivers_by_slice_tenant_uuid = {} 
        self._slivers_by_urn = {} 

        self._virtual_machines_by_urn = {} 
        self._network_interfaces_by_virtual_machine_urn = {} 

        self._network_interfaces_by_urn = {} 
        self._network_link_by_network_interface_urn = {} 
        self._virtual_machine_by_network_interface_urn = {}

        self._network_links_by_urn = {}


    def decode(self, json_object):
#        print "DECODE : " + str(type(json_object)) + " " + str(json_object) 
        if isinstance(json_object, dict) and json_object.has_key("__type__"):
            obj_type = json_object["__type__"]

            if(obj_type == "Slice"):
                slice = Slice(json_object["slice_urn"])
                tenant_uuid = json_object['tenant_uuid']
                slice.setTenantUUID(tenant_uuid)
                slice.setTenantName(json_object["tenant_name"])
                tenant_admin_name = json_object['tenant_admin_name']
                tenant_admin_pwd = json_object['tenant_admin_pwd']
                tenant_admin_uuid = json_object['tenant_admin_uuid']
                slice.setTenantAdminInfo(tenant_admin_name, tenant_admin_pwd, \
                                             tenant_admin_uuid)
                slice.setControlNetInfo(json_object["control_net_info"])
                slice.setTenantRouterName(json_object["tenant_router_name"])
                slice.setTenantRouterUUID(json_object["tenant_router_uuid"])
#                slice.setControlNetAddress(json_object["control_net_address"])
                slice.setUserURN(json_object["user_urn"])
                expiration_timestamp = json_object['expiration']
                expiration_time = \
                    datetime.datetime.fromtimestamp(expiration_timestamp)
                slice.setExpiration(expiration_time)
                slice.setManifestRspec(json_object["manifest_rspec"])
                slice.setRequestRspec(json_object["request_rspec"])
                slice._last_subnet_assigned = json_object['last_subnet_assigned']
                slice._next_vm_num = json_object['next_vm_num']
                slice.setControllerURL(json_object['controller_url'])
                
                self._slivers_by_slice_tenant_uuid[tenant_uuid] = \
                    json_object['slivers']

                self._slices_by_tenant_uuid[tenant_uuid] = slice
                
                
                return slice;

            if(obj_type == "VirtualMachine"):
                # VM wants a slice in its constructor
                slice_tenant_uuid = json_object['slice']
                uuid = json_object['uuid']
                slice = self._slices_by_tenant_uuid[slice_tenant_uuid]
                vm = VirtualMachine(slice, uuid)
                vm.setName(json_object["name"])
                vm.setUUID(uuid)
                vm._sliver_urn = json_object["sliver_urn"]
                sliver_urn = vm._sliver_urn
                expiration_timestamp = json_object['expiration']
                expiration_time = \
                    datetime.datetime.fromtimestamp(expiration_timestamp)
                vm.setExpiration(expiration_time)
                vm.setAllocationState(json_object["allocation_state"])
                vm.setOperationalState(json_object["operational_state"])
                vm.setControlNetAddr(json_object["control_net_addr"])
                vm._installs = json_object["installs"]
                vm._executes = json_object["executes"]
                vm._ip_last_octet = json_object["last_octet"]
                vm._os_image = json_object["os_image"]
                vm._os_type = json_object["os_type"]
                vm._os_version = json_object["os_version"]
                vm._flavor = json_object["vm_flavor"]
                vm.setHost(json_object['host'])
                
                # network_interfaces
                self._network_interfaces_by_virtual_machine_urn[sliver_urn]  = \
                    json_object['network_interfaces']

                self._virtual_machines_by_urn[sliver_urn] = vm
                self._slivers_by_urn[sliver_urn] = vm

                return vm

            if(obj_type == "NetworkInterface"):
                # network interface  wants a slice and VM in its constructor
                slice_tenant_uuid = json_object['slice']
                virtual_machine_urn = json_object['virtual_machine']
                uuid = json_object['uuid']
                slice = self._slices_by_tenant_uuid[slice_tenant_uuid]
                nic = NetworkInterface(slice, None, uuid)
                nic.setName(json_object["name"])
                nic._sliver_urn = json_object["sliver_urn"]
                sliver_urn = nic._sliver_urn
                expiration_timestamp = json_object['expiration']
                expiration_time = \
                    datetime.datetime.fromtimestamp(expiration_timestamp)
                nic.setExpiration(expiration_time)
                nic.setAllocationState(json_object["allocation_state"])
                nic.setOperationalState(json_object["operational_state"])
                nic._device_number = json_object["device_number"]
                nic.setMACAddress(json_object["mac_address"])
                nic.setIPAddress(json_object["ip_address"])
                nic.setVLANTag(json_object["vlan_tag"])

                # vm
                self._virtual_machine_by_network_interface_urn[sliver_urn] = virtual_machine_urn
            
                # link
                self._network_link_by_network_interface_urn[sliver_urn] = json_object['link']

                self._network_interfaces_by_urn[sliver_urn] = nic
                self._slivers_by_urn[sliver_urn] = nic

                return nic;

            if(obj_type == "NetworkLink"):
                # Link wants a slice 
                slice_tenant_uuid = json_object['slice']
                uuid = json_object['uuid']
                slice = self._slices_by_tenant_uuid[slice_tenant_uuid]
                link = NetworkLink(slice, uuid)
                link.setName(json_object["name"])
                link._sliver_urn = json_object["sliver_urn"]
                sliver_urn = link._sliver_urn
                expiration_timestamp = json_object['expiration']
                expiration_time = \
                    datetime.datetime.fromtimestamp(expiration_timestamp)
                link.setExpiration(expiration_time)
                link.setAllocationState(json_object["allocation_state"])
                link.setOperationalState(json_object["operational_state"])
                link.setSubnet(json_object["subnet"])
                link.setNetworkUUID(json_object["network_uuid"])
                link.setSubnetUUID(json_object["subnet_uuid"])
                link.setVLANTag(json_object['vlan_tag'])
                
                self._network_links_by_urn[sliver_urn] = link
                self._slivers_by_urn[sliver_urn] = link
                
                return link

            return json_object

    # Re-link the objects
    # 1. Resolve the references for the VM's
    # 2. Resolve the references for the NIC's
    # 3. Resolve the references for the Link's
    def resolve(self):

    # Restore virtual_machine <=> network_interfaces link
        for virtual_machine_urn in self._virtual_machines_by_urn.keys():
            virtual_machine = self._slivers_by_urn[virtual_machine_urn]
            network_interfaces = \
                [self._slivers_by_urn[nic_urn] \
                     for nic_urn in self._network_interfaces_by_virtual_machine_urn[virtual_machine_urn]]
            virtual_machine._network_interfaces = network_interfaces
            for nic in network_interfaces: nic.setVM(virtual_machine)

    # Restore the nic <=> link nic <=> vm
        for network_interface_urn in self._network_interfaces_by_urn.keys():
            network_interface = self._slivers_by_urn[network_interface_urn]
            link_urn = self._network_link_by_network_interface_urn[network_interface_urn]
            if link_urn:
                link = self._slivers_by_urn[link_urn]
                network_interface.setLink(link)
                link.addEndpoint(network_interface)

def read_slices(filename):
    file = open(filename, "r")
    data = file.read()
    file.close()
    json_data = json.loads(data)

    # This should be a list of JSON-enocded objects
    # Need to turn this into a list of objects
    # Resolve links among them

    decoder = GramJSONDecoder()
    for json_object in json_data: 
        decoder.decode(json_object)
    decoder.resolve()

    # Return a  dictionary of all slices indexed by slice_urn
    slices = dict()
    for slice in decoder._slices_by_tenant_uuid.values():
        slice_urn = slice.getSliceURN()
        slices[slice_urn] = slice

    return slices

