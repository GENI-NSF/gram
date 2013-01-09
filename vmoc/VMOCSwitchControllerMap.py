from pox.core import core
from VMOCSwitchConnection import VMOCSwitchConnection
from VMOCControllerConnection import VMOCControllerConnection

log = core.getLogger() # Use the central logging service

# Class that maintains list of all switch connections 
#    and controller connections (one per switch)
class VMOCSwitchControllerMap(object):

    def __init__(self):
        self._controller_urls = []
        self._switch_connections = []
        self._controller_connections_by_url = {}
        self._controller_connections_by_switch = {}
        self._switch_connection_by_controller = {}

    # Find the controller connections associated 
    # with a given switch connection
    def lookup_controllers_for_switch(self, switch_conn):
        return self._controller_connections_by_switch[switch_conn]

    # Find the switch connection associated with the 
    # given controller connection
    def lookup_switch_for_controller(self, controller_conn):
        return self._switch_connection_by_controller[controller_conn]

    # Create a new controller connection at given URL 
    # and associate with all current switches
    def add_controller(self, controller_url, open_on_create=True):
        # Add controller url to list of urls
        self._controller_urls.append(controller_url)
        self._controller_connections_by_url[controller_url] = list()

        # Create a new controller connection for each switch
        for switch_conn in self._switch_connections:
            controller_conn = VMOCControllerConnection(controller_url, \
                                                           switch_conn, \
                                                           open_on_create)
            self._controller_connections_by_url[controller_url].\
                append(controller_conn)
            self._controller_connections_by_switch[switch_conn].\
                append(controller_conn)
            self._switch_connection_by_controller[controller_conn] \
                = switch_conn

    # Remove all controller connection at given URL
    def remove_controller(self, controller_url):

        # Remove controller from list of controllers by URL
        if self._controller_connections_by_url.has_key(controller_url) :
            del self._controller_connections_by_url[controller_url]

        # Remove controller from list of controllers by switch
        # And remove switch connection for this controller
        for switch in self._switch_connections:
            conns = self._controller_connections_by_switch[switch];
            for conn in conns:
                if conn.getURL() == controller_url:
                    conns.remove(conn)
                    if self._switch_connection_by_controller.has_key(conn):
                        del self._switch_connection_by_controller[conn]

        # Remove URL from list of urls
        if controller_url in self._controller_urls:
            self._controller_urls.remove(controller_url)


    # Add a new switch connection to the map, 
    # adding associated controller connections
    def add_switch(self, switch_conn, open_on_create=True):

        dpid = switch_conn.getConnection().dpid
        log.debug("Adding switch DPID = " + str(dpid))

        # Add connection to list of switch connection
        self._switch_connections.append(switch_conn)
        self._controller_connections_by_switch[switch_conn] = list()
        
        # For each current conenction URL, create a new client connection
        # And link it  up
        for controller_url in self._controller_urls:
            controller_conn = \
                VMOCControllerConnection(controller_url, switch_conn, \
                                             open_on_create)
            self._controller_connections_by_switch[switch_conn].\
                append(controller_conn)
            self._controller_connections_by_url[controller_url].\
                append(controller_conn)
            self._switch_connection_by_controller[controller_conn] = \
                switch_conn

    # Remove switch connection from map 
    # and all associated controller connections
    def remove_switch(self, switch_conn):
        # Remove switch from list of switch connections
        if switch_conn in self._switch_connections:
            self._switch_connections.remove(switch_conn)
            
        # Remove controller associated with switch from table
        # of controllers by URL
        # And remove association of this switch with controller
        if self._controller_connections_by_switch.has_key(switch_conn):
            for controller_conn in \
                    self._controller_connections_by_switch[switch_conn]:
                url = controller_conn.getURL()
                if self._controller_connections_by_url.has_key(url):
                    conns = self._controller_connections_by_url[url]
                    if controller_conn in conns:
                        conns.remove(controller_conn)
                        del self._switch_connection_by_controller\
                            [controller_conn]
        # Remove controller associated with switch connection
        del self._controller_connections_by_switch[switch_conn]

    # Dump contents of map (for testing)
    def dump(self):
        print "VMOCSwitchControllerMap:"
        print  "  Controllers:"
        for url in self._controller_urls:
            print "      " + url
            for controller in self._controller_connections_by_url[url]:
                print "         " + str(controller)
                switch = self._switch_connection_by_controller[controller]
                print "            " + str(switch)
        print "   Switches:"
        for switch in self._switch_connections:
            print "      " + str(switch)
            for controller in self._controller_connections_by_switch[switch]:
                print "         " + str(controller)



# Singleton instance
_switch_controller_map = VMOCSwitchControllerMap()

# static methods

# Find the controller connections associated with a given switch connection
def lookup_controllers_for_switch_connection(switch_conn):
    return _switch_controller_map.lookup_controllers_for_switch(switch_conn)

# Find the switch connection associated with the given controller connection
def lookup_switch_for_controller_connection(controller_conn):
    return _switch_controller_map.lookup_switch_for_controller(controller_conn)

# Create a new controller connection at given URL 
# and associate with all current switches
def add_controller_connection(controller_url, open_on_create=True):
    _switch_controller_map.add_controller(controller_url, open_on_create)

# Remove all controller connection at given URL
def remove_controller_connection(controller_url):
    _switch_controller_map.remove_controller(controller_url)

# Add a new switch connection to the map, 
# adding associated controller connections
def add_switch_connection(switch_conn, open_on_create=True):
    _switch_controller_map.add_switch(switch_conn, open_on_create)

# Remove switch connection from map and all associated controller connections
def remove_switch_connection(switch_conn):
    _switch_controller_map.remove_switch(switch_conn)

# Dump contents of current switch controller map state
def dump_switch_controller_map():
    _switch_controller_map.dump()

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

    remove_controller_connection(url1)
    print("T5:")
    dump_switch_controller_map()

    remove_switch_connection(s1)
    print("T6:")
    dump_switch_controller_map()

    remove_switch_connection(s2)
    print("T7:")
    dump_switch_controller_map()

    remove_controller_connection(url2)
    print("T8:")
    dump_switch_controller_map()



if __name__ == "__main__":
    switch_controller_map_test()


