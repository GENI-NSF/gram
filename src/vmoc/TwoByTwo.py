#!/usr/bin/python

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

from mininet.topo import Topo, Node
import json
import pdb


class TwoByTwo( Topo ):
    "Two switches, each of which have two nodes attached to them"

    def __init__( self, enable_all = True ):
        "Create custom topo : TwoByTwo."

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

        # Print out the slice config files for VMOC

        self.generateSliceConfig('S1', None, 101, [1, 4])
#        self.generateSliceConfig('S2', 'http://localhost:9001', 102, [2, 3])
        self.generateSliceConfig('S2', None, 102, [2, 3])


    # slice_config.json
    # And the slice topology configuration 
    #    {slice_id:slice_id, controller_url:controller_url,
    #        vlans:[{vlan_id:vlan_id, mac:mac}]
    def generateSliceConfig(self, slice_id, controller_url, vlan_id, nodes):

        switches = Topo.switches(self)
        hosts = Topo.hosts(self)

        macs = []
        for n in nodes:
            if not n in hosts: continue
            mac = '00:00:00:00:00:%02d' % n
            macs.append(mac)

        vlan = {'vlan_id' : vlan_id, 'macs' : macs}
        vlans = [vlan]
        config = {'slice_id' : slice_id,
                  'controller_url' : controller_url,
                  'vlans' : vlans}


        filename = '/tmp/slice_config_%s.json' % slice_id
        self.dumpAsJson(config, filename)

    def dumpAsJson(self, data, filename):
#        print "DAJ " + str(data) + " " + filename
        file = open(filename, 'w')
        json_data = json.dumps(data)
        file.write(json_data)
        file.close()

topos = { 'TwoByTwo': ( lambda: TwoByTwo() ) }
