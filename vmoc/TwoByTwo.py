from mininet.topo import Topo, Node
import json
import pdb


class TwoByTwo( Topo ):
    "Two switches, each of which have two nodes attached to them"

    def __init__( self, enable_all = True ):
        "Create custom topo."

        # Add default members to class.
        super( TwoByTwo, self ).__init__()

        # Set Node IDs for hosts and switches
        leftAHost = 1
        leftBHost = 2
        rightCHost = 3
        rightDHost = 4
        leftSwitch = 5
        rightSwitch = 6
        topSwitch = 7

        # Add nodes
        self.add_node( leftSwitch, Node( is_switch=True ) )
        self.add_node( rightSwitch, Node( is_switch=True ) )
        self.add_node( topSwitch, Node( is_switch=True ) )
        self.add_node( leftAHost, Node( is_switch=False ) )
        self.add_node( leftBHost, Node( is_switch=False ) )
        self.add_node( rightCHost, Node( is_switch=False ) )
        self.add_node( rightDHost, Node( is_switch=False ) )

        # Add edges
        self.add_edge( leftAHost, leftSwitch )
        self.add_edge( leftBHost, leftSwitch )

        self.add_edge( rightSwitch, rightCHost )
        self.add_edge( rightSwitch, rightDHost )

        self.add_edge( leftSwitch, topSwitch )
        self.add_edge( rightSwitch, topSwitch )

        # Consider all switches and hosts 'on'
        self.enable_all()

        # Print out the config files for VMOC
        # fixed and slice-specific

        self.generateFixedConfig()
        self.generateSliceConfig('S1', 'http://localhost:9001', 101, [1, 4])
        self.generateSliceConfig('S2', 'http://localhost:9002', 102, [2, 3])

    # fixed_config.json:
    # There is the fixed configuration of switches/ports/nodes
    #    For each switch
    #      {dpid:DPID, links:{port:port, is_node:is_node, id:dpid/node_id}}
    def generateFixedConfig(self):
        switches = Topo.switches(self)
        nodes = Topo.nodes(self)
        hosts = Topo.hosts(self)

        config = list()

        for s in switches:
            dpid = s
            links_info = list()
            for n in nodes:
                if n in hosts: continue
                ports = Topo.port(self, s, n)
                if ports == None: continue
                port = ports[0]
                is_node = n in hosts
                link_info = {'port' : port, 'is_node' : is_node, 'id' : n}
                links_info.append(link_info)
            node_config = {'dpid' : dpid, 'links' : links_info}
            config.append(node_config)
                        
        self.dumpAsJson(config, '/tmp/fixed_config.json')

    # slice_config.json
    # And the slice topology configuration 
    #    {slice_id:slice_id, controller_url:controller_url,
    #        vlan_id:vlan_id, nodes:[{mac:mac, switch:switch, port:port}]
    #    slice_id and controller_url VLAN_id are fixed
    #    node_id, MAC, PORT are from config
    #    i.e. what port is this node connected to on the node's switch
    def generateSliceConfig(self, slice_name, controller_url, vlan_id, nodes):

        switches = Topo.switches(self)
        hosts = Topo.hosts(self)

        nodes_info = list()
        for n in nodes:
            if not n in hosts: continue
            mac = '00:00:00:00:00:%02d' % n
            for s in switches:
                ports = Topo.port(self, s, n)
                if ports == None: continue
                port = ports[0]
                switch_id = s
                node_info = {'mac' : mac, 'switch' : switch_id, 
                             'port' : port}
                nodes_info.append(node_info)

        config = {'slice_id' : slice_name, 
                  'controller_url' : controller_url, 
                  'vlan_id' : vlan_id,
                  'nodes' : nodes_info}

        filename = '/tmp/slice_config_%s.json' % slice_name
        self.dumpAsJson(config, filename)

    def dumpAsJson(self, data, filename):
#        print "DAJ " + str(data) + " " + filename
        file = open(filename, 'w')
        json_data = json.dumps(data)
        file.write(json_data)
        file.close()

topos = { 'TwoByTwo': ( lambda: TwoByTwo() ) }
