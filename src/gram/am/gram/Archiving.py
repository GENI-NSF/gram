# Routines and helper classes for saving/restoring AggregateState
# to/from files using JSON

import json
import pdb
from Resources import Slice, VirtualMachine, NetworkLink, NetworkInterface
from AggregateState import AggregateState
from AllocationManager import AllocationManager

class GramJSONEncoder(json.JSONEncoder):
    def default(self, o):
#        print "In Default " + str(o)
        if isinstance(o, AggregateState):
            return {
                "__type__":"AggregateState",
                "sequence_number": o._sequence_number,
                "archive_directory": o._archive_directory,
                "public_vlan_tags": o._public_vlan_tags,
                "vlan_manager": o._vlan_tag_manager,
                "public_ip_addresses": o._public_ip_addresses,
                "ip_address_manager": o._ip_address_manager,
                "flavor_capacities": o._flavor_capacities,
                "flavor_manager": o._flavor_manager,
                "flavor_allocations": o._flavor_allocations,
                "parameters": o._parameters,
                "slivers_by_urn": o._slivers_by_urn
                }
                
        if isinstance(o, AllocationManager):
            return {
                "__type__":"AllocationManager",
                "max_slivers": o._max_slivers,
                "resources": o._resources
                }

        if isinstance(o, Slice):
            return {
                "__type__":"Slice", 
                "slice_urn":o.getSliceURN(),
                "sa_urn":o.getSAURN(), 
                "user_urn":o.getUserURN(),
                "expiration":o.getExpiration(),
                "tenant_id":o.getTenantID(),
                "router_id":o.getRouterID(),
                "manifest_rspec":o.getManifestRSpec()
                }

        if isinstance(o, VirtualMachine):
            return {"__type__":"VirtualMachine",
                    "uuid":o._uuid,
                    "component_id":o._component_id,
                    "slice":o._slice,
                    "expiration":o._expiration,
                    "control_net_addr":o._control_net_addr,
                    "node_name":o._node_name,
                    "network_interfaces":o._network_interfaces,
                    "authorized_user_urns":o._authorized_user_urns,
                    "installs":o._installs,
                    "executes":o._executes,
                    "allocation_state":o._allocation_state,
                    "operational_state":o._operational_state,
                    "flavor":o._flavor,
                    "image_id":o._image_id
                    }
        

        if isinstance(o, NetworkInterface):
            return {"__type__":"NetworkInterface",
                    "uuid":o._uuid,
                    "component_id":o._component_id,
                    "slice":o._slice,
                    "expiration":o._expiration,
                    "name":o._name,
                    "device_number":o._device_number,
                    "mac_address":o._mac_address,
                    "ip_address":o._ip_address,
# Avoid circular reference
#                    "host":o._host,
                    "virtual_eth_name":o._virtual_eth_name
# Avoid circular reference
#                    "link":o._link 
                    }


        if isinstance(o, NetworkLink):
           return {"__type__":"NetworkLink",
                    "uuid":o._uuid,
                    "component_id":o._component_id,
                    "slice":o._slice,
                    "expiration":o._expiration,
                    "name":o._name,
                    "subnet":o._subnet,
                    "endpoints":o._endpoints,
                    "network_id":o._network_id,
                    "vlan_tag":o._vlan_tag
                   }

def  gram_json_object_hook(json_object):

#    print "GJOH : " + str(json_object) + " " + str(type(json_object))
    if isinstance(json_object, dict) and json_object.has_key("__type__"):
        obj_type = json_object["__type__"]

        if(obj_type == "AggregateState"):
            state = AggregateState(None)
            state._sequence_number = json_object["sequence_number"]
            state._archive_directory = json_object["archive_directory"]
            state._public_vlan_tags = json_object["public_vlan_tags"]
            state._vlan_tag_manager = json_object["vlan_manager"]
            state._public_ip_addresses = json_object["public_ip_addresses"]
            state._ip_address_manager = json_object["ip_address_manager"]
            state._flavor_capacities = json_object["flavor_capacities"]
            state._flavor_manager = json_object["flavor_manager"]
            state._flavor_allocations = json_object["flavor_allocations"]
            state._parameters = json_object["parameters"]
            state._slivers_by_urn = json_object["slivers_by_urn"]
            return state

        if(obj_type == "AllocationManager"):
            max_slivers = json_object["max_slivers"]
            resources = json_object["resources"]
            am = AllocationManager(max_slivers);
            am._resources = resources;
            return am

        if(obj_type == "Slice"):
            slice = Slice(json_object["slice_urn"],
            json_object["sa_urn"],
            json_object["user_urn"],
            json_object["expiration"],
            json_object["tenant_id"],
            json_object["router_id"],
            json_object["manifest_rspec"])
            return slice;

        if(obj_type == "VirtualMachine"):
            vm = VirtualMachine(json_object["uuid"],
            json_object["component_id"],
            json_object["slice"],
            json_object["expiration"],
            json_object["control_net_addr"],
            json_object["node_name"],
            json_object["installs"],
            json_object["executes"],
            json_object["network_interfaces"],
            json_object["authorized_user_urns"],
            json_object["allocation_state"],
            json_object["operational_state"],
            json_object["flavor"],
            json_object["image_id"])
            return vm

        if(obj_type == "NetworkInterface"):
            nic = NetworkInterface(json_object["uuid"],
            json_object["component_id"],
            json_object["slice"],
            json_object["expiration"],
            json_object["name"],
            json_object["device_number"],
            json_object["mac_address"],
                                   json_object["ip_address"],
#                                   json_object["host"],
                                   None, # Avoid circular reference
                                   json_object["virtual_eth_name"],
#                                   json_object["link"]
                                   None # Avoid circular reference
                                   )
            return nic

        if(obj_type == "NetworkLink"):
            link = NetworkLink(json_object["uuid"],
            json_object["component_id"],
            json_object["slice"],
            json_object["expiration"],
                               json_object["name"],
                               json_object["subnet"],
                               json_object["endpoints"],
                               json_object["network_id"],
                               json_object["vlan_tag"])
            return link;

    return json_object


def write_aggregate_state(filename, aggregate_state):
#    print "WAS.CALL " + str(aggregate_state) + " " + filename
    file = open(filename, "w")
    data = GramJSONEncoder().encode(aggregate_state);
    file.write(data)
    file.close();
#    print "WAS.DATA = " + str(data)

def resolve_slivers(slivers_by_urn, slivers):
    new_slivers = list()
    for sliver in slivers:
        sliver_urn = sliver.getComponentID()
        new_sliver = slivers_by_urn[sliver_urn]
        new_slivers.append(new_sliver)
    return new_slivers

def read_aggregate_state(filename):
    file = open(filename, "r")
    data = file.read()
    file.close()

    am = json.loads(data, object_hook=gram_json_object_hook)

    # Now relink the NetworkLink and NetworkInterface and VM objects
    # to resolve / reestablish circular dependencies
    # 
    # 1. Go through all the slivers in am.getSliversByURN
    # 2. Go to each VM and find the NI's corresponding 
    #       to VM.getNetworkInterfaces. 
    # 3. Then call ni.setHost(vm), vm.setNetworkInterfaces(nis)
    # 4. Go to each NL and find the NI's corresponding
    #       to NI.getEndpoints
    # 5. Then call nl.setEndpoints(nl) and ni.setLink(nl)
    #
    slivers_by_urn = am.getSliversByURN();
    for sliver in slivers_by_urn.values():
        if isinstance(sliver, VirtualMachine):
            new_nis = resolve_slivers(slivers_by_urn, 
                                      sliver.getNetworkInterfaces())
            for ni in new_nis:
                ni.setHost(sliver)
            sliver.setNetworkInterfaces(new_nis);
        if isinstance(sliver, NetworkLink):
            new_nis = resolve_slivers(slivers_by_urn,
                                      sliver.getEndpoints())
            for ni in new_nis:
                ni.setLink(sliver)
            sliver.setEndpoints(new_nis)

    return am
