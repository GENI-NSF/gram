import pdb
import socket
import threading
import time

from pox.core import core
from VMOCSwitchConnection import VMOCSwitchConnection
from VMOCControllerConnection import VMOCControllerConnection
from VMOCSliceRegistry import *


log = core.getLogger() # Use the central logging service

# Class that maintains list of all switch connections 
#    and controller connections (one per managed vlan per switch)
class VMOCSwitchControllerMap(object):

    def __init__(self):
        self._switch_connections = []
        self._controller_connections_by_switch = {}
        self._controller_connections_by_vlan = {}
        self._switch_connection_by_controller = {}

    # Find the controller connections associated 
    # with a given switch connection
    def lookup_controllers_for_switch(self, switch_conn):
        if not self._controller_connections_by_switch.has_key(switch_conn):
            return None
        return self._controller_connections_by_switch[switch_conn]


    # Find the switch connection associated with the 
    # given controller connection
    def lookup_switch_for_controller(self, controller_conn):
        return self._switch_connection_by_controller[controller_conn]

    # Add a new controller connection for given switch connection
    def add_controller_connection(self, controller_conn, switch_conn):
        self._controller_connections_by_switch[switch_conn].append(controller_conn)
        self._switch_connection_by_controller[controller_conn] = switch_conn
        vlan = controller_conn.getVLAN()
        if not self._controller_connections_by_vlan.has_key(vlan):
            self._controller_connections_by_vlan[vlan] = list()
        self._controller_connections_by_vlan[vlan].append(controller_conn)

    # Create a new controller connection at given URL 
    # and associate with all current switches
    def create_controller_connection(self, controller_url, vlan, \
                                         open_on_create=True):

        # Creates a thread to try to connect, and wait until controller is up
        ControllerURLCreationThread(controller_url, vlan, self).start()


    # Remove a particular controller connection
    def remove_controller_connection(self, controller_conn):

        # Might have been called by switch connection or controller connection
        # detecting that we're down
        if not self._switch_connection_by_controller.has_key(controller_conn): 
            return

        switch_conn = self._switch_connection_by_controller[controller_conn]
        vlan = controller_conn.getVLAN()

        assert self._switch_connection_by_controller.has_key(controller_conn)
        del self._switch_connection_by_controller[controller_conn]

        assert self._controller_connections_by_switch.has_key(switch_conn)
        controllers_for_switch = self._controller_connections_by_switch[switch_conn]
        controllers_for_switch.remove(controller_conn)
        self._controller_connections_by_switch[switch_conn] = controllers_for_switch

        assert self._controller_connections_by_vlan.has_key(vlan)
        controllers_for_vlan = self._controller_connections_by_vlan[vlan]
        controllers_for_vlan.remove(controller_conn)
        self._controller_connections_by_vlan[vlan] = controllers_for_vlan

    # Remove all controller connections for a given slice
    def remove_controller_connections_for_slice(self, slice_id):
        slice_config = slice_registry_lookup_slice_config_by_slice_id(slice_id)
        for vc in slice_config.getVLANConfigurations():
            vlan = vc.getVLANTag()
            if self._controller_connections_by_vlan.has_key(vlan):
                controller_connections = \
                    self._controller_connections_by_vlan[vlan]
                for controller_connection in controller_connections:
#                print "   *** REMOVING " + str(controller_connection) + " ***"
                    self.remove_controller_connection(controller_connection)

    # Add a new switch connection to the map, 
    # adding associated controller connections
    def add_switch(self, switch_conn, open_on_create=True):

        dpid = switch_conn.getConnection().dpid
        log.debug("Adding switch DPID = " + str(dpid))

        # Add connection to list of switch connection
        self._switch_connections.append(switch_conn)
        self._controller_connections_by_switch[switch_conn] = list()
        
        # For each vlan configuration in each
        # slice configuration, create a new client connection
        for slice_config in slice_registry_get_slice_configs():
            for vc in slice_config.getVLANConfigurations():
                vlan = vc.getVLANTag()
                controller_url = vc.getControllerURL()
                controller_conn = VMOCControllerConnection(controller_url, \
                                                               switch_conn, \
                                                               vlan, \
                                                               open_on_create)
                self.add_controller_connection(controller_conn, switch_conn)
                    
    # Remove switch connection from map 
    # and all associated controller connections
    def remove_switch(self, switch_conn, close_controller_connections=False):
        # Remove switch from list of switch connections
        if switch_conn in self._switch_connections:
            self._switch_connections.remove(switch_conn)

        # Remove controller associated with switch from table
        # of controllers by URL
        # And remove association of this switch with controller
        if self._controller_connections_by_switch.has_key(switch_conn):
            for controller_conn in \
                    self._controller_connections_by_switch[switch_conn]:
                self.remove_controller_connection(controller_conn)
                if close_controller_connections:
                    controller_conn.close()

    # Dump contents of map (for testing)
    def dump(self, print_results = False):
        image = "VMOCSwitchControllerMap:" + "\n"
        image +="   Switches:" + "\n"
        for switch in self._switch_connections:
            image += "      " + str(switch) + "\n"
            for controller in self._controller_connections_by_switch[switch]:
                image += "         " + str(controller) + "\n"
        image += "   Switches(unindexed):" + "\n"
        for switch_connection in self._switch_connections:
            image += "     " + str(switch_connection) + "\n"
        image += "   Switches (by Controller):" + "\n"
        for controller_conn in self._switch_connection_by_controller.keys():
            image += "     " + str(controller_conn) + "\n"
            switch_conn = self._switch_connection_by_controller[controller_conn]
            image += "          " + str(switch_conn) + "\n"
        image += "   Controllers (by VLAN) " + "\n"
        for vlan in self._controller_connections_by_vlan.keys():
            image += "     " + str(vlan) + "\n "
            for conn in self._controller_connections_by_vlan[vlan]:
                image += "         " + str(conn) + "\n"
        if print_results:
            print image
        return image


# Singleton instance
_switch_controller_map = VMOCSwitchControllerMap()

# static methods

# Find the controller connections associated with a given switch connection
def lookup_controllers_for_switch_connection(switch_conn):
    return _switch_controller_map.lookup_controllers_for_switch(switch_conn)

# Find the switch connection associated with the given controller connection
def lookup_switch_for_controller_connection(controller_conn):
    return _switch_controller_map.lookup_switch_for_controller(controller_conn)

# Create a new controller connection at given URL and VLAN
# and associate with all current switches
def create_controller_connection(controller_url, vlan, open_on_create=True):
    _switch_controller_map.create_controller_connection(controller_url, vlan, open_on_create)

# Remove all controllere connections for a given slice id
def remove_controller_connections_for_slice(slice_id):
    _switch_controller_map.remove_controller_connections_for_slice(slice_id)

# Remove this specific controller connection
def remove_controller_connection(controller_conn):
    _switch_controller_map.remove_controller_connection(controller_conn)

# Add a new switch connection to the map, 
# adding associated controller connections
def add_switch_connection(switch_conn, open_on_create=True):
    _switch_controller_map.add_switch(switch_conn, open_on_create)

# Remove switch connection from map and all associated controller connections
def remove_switch_connection(switch_conn, close_controller_connections=False):
    _switch_controller_map.remove_switch(switch_conn, close_controller_connections)

# Dump contents of current switch controller map state
def dump_switch_controller_map(print_results=False):
    return _switch_controller_map.dump(print_results)

# Class that that spanws a thread and creates a connection to a controller
# URL when the URL responds
class ControllerURLCreationThread(threading.Thread):
    def __init__(self, controller_url, vlan, scmap):
        threading.Thread.__init__(self)
        host, port = VMOCControllerConnection.parseURL(controller_url)
        self._controller_url = controller_url
        self._host = host
        self._port = port
        self._vlan = vlan
        self._scmap = scmap
        self._running = False

    def run(self):
        self._running = True
        while self._running:

            url_responsive = False
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((self._host, self._port))
                sock.close()
                url_responsive = True
            except Exception as e:
                log.info("Controller URL unresponsive: " + \
                             self._controller_url + " " + str(e))

            if url_responsive:
                # Once the controller is avaiable, 
                # check that the controller and the vlan are still paired
                # Otherwise, don't create connection
                slice_config = \
                    slice_registry_lookup_slice_config_by_vlan(self._vlan)
                if not slice_config or not slice_config.contains(self._controller_url, self._vlan):
                    log.info("VLAN/Controller mapping changed : " + \
                                 " not startng connection" + \
                                 str(self._controller_url) + " " + str(self._vlan))
                    self._running = False
                else:
                    # Create a new controller connection for each switch
                    for switch_conn in self._scmap._switch_connections:
                        controller_conn = \
                            VMOCControllerConnection(self._controller_url, \
                                                         switch_conn, \
                                                         self._vlan, True)
                        self._scmap.add_controller_connection(controller_conn, \
                                                                  switch_conn)
                    self._running = False
            else:
                time.sleep(1)

        log.debug("Exiting ControllerURLCreationThread");


# Test procedure:
# Add switch
# Add controller
# Add controller
# Add switch
# Remove controller
# Remove switch
# Remove switch
# Remove controller
def switch_controller_map_test():
    print "VMOCSwitchControlllerMap..."

    print("T0:")
    dump_switch_controller_map()

    s1 = VMOCSwitchConnection(None)
    add_switch_connection(s1, False)
    print("T1:")
    dump_switch_controller_map()

    url1 = "http://localhost:8001"
    add_controller_connection(url1, False)
    print("T2:")
    dump_switch_controller_map()

    url2 = "http://localhost:8002"
    add_controller_connection(url2, False)
    print("T3:")
    dump_switch_controller_map()

    s2 = VMOCSwitchConnection(None)
    add_switch_connection(s2, False)
    print("T4:")
    dump_switch_controller_map()

    remove_switch_connection(s1)
    print("T6:")
    dump_switch_controller_map()

    remove_switch_connection(s2)
    print("T7:")
    dump_switch_controller_map()


if __name__ == "__main__":
    switch_controller_map_test()


