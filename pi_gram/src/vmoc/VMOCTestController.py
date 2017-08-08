#!/usr/bin/python

#----------------------------------------------------------------------
# Copyright (c) 2013-2016 Raytheon BBN Technologies
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

# A test controller for 1-30-2013 demonstration of
# Gram/VMOC managing experimenter controllers

# First, there are tests that don't involve this controller
# 1- No controller (no VMOC)
# 2- Slice not regisgtered with VMOC
# 2- Slice but null Controller  (use default)

# Then there are several test 'modes' provided by this controller
# 'asterisk' - Turn all characters in header into '*'
# 'portmod' - Modifies the port of 5000 traffic to 5001
# 'bad' - Generate flow mods and packets not within your VLAN
# 'simple' - Just do a simple learning switch , W/O writing flow mods to OF switch
# 'stripped' - Pass packets without any VLAN tagging


from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.openflow import *
import string
import time
import threading
import pdb
from SimpleLearningSwitch import SimpleLearningSwitch
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.vlan import vlan
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.arp import arp
from pox.lib.packet.tcp import tcp

log = core.getLogger() # Use central logging service


IP_START = ethernet.MIN_LEN + vlan.MIN_LEN
TCP_HEADER_START = ethernet.MIN_LEN + vlan.MIN_LEN + ipv4.MIN_LEN
TCP_PAYLOAD_START = ethernet.MIN_LEN + vlan.MIN_LEN + ipv4.MIN_LEN + 32
        
class VMOCTestController(SimpleLearningSwitch):

    def __init__(self, connection, test_mode):
        SimpleLearningSwitch.__init__(self, connection, False)
        self._test_mode = test_mode
        self._transtable = \
        string.maketrans('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                         '**************************************************************')
        self._connection = connection;

    def _handle_PacketIn(self, event):
        log.debug("Got a packet : " + str(event))
        if self._test_mode == 'asterisk':
            self._handle_PacketIn_asterisk(event)
        elif self._test_mode == 'simple':
            self._handle_PacketIn_simple(event)
        elif self._test_mode == 'portmod':
            self._handle_PacketIn_portmod(event)
        elif self._test_mode == 'bad':
            self._handle_PacketIn_bad(event)
        elif self._test_mode == 'stripped':
            self._handle_PacketIn_stripped(event)
        else:
            print("Unknwon test mode : " + self._test_mode)

    # This test changes all ASCII digits in the header to '*'
    # This case doesn't write any flow mods: all traffic goes through controller
    def _handle_PacketIn_asterisk(self, event):
        data, eth_packet, vlan_packet, ip_packet, tcp_packet = self.parsePacket(event)

        ofp = event.ofp

        if tcp_packet and tcp_packet.dstport == 5000 and len(tcp_packet.payload) > 0:
            payload = tcp_packet.payload
            new_payload = payload.translate(self._transtable)
#           new_payload = payload
            new_tcp_data = tcp_packet.hdr(new_payload) + new_payload
            new_tcp = tcp(raw = new_tcp_data, prev = ip_packet)
            new_tcp.parse(new_tcp_data)
            new_tcp.hdr(new_payload)
#            print "*** TCP " + payload + " " + new_payload + " " + \
#                str(len(payload)) + " " + str(len(new_payload)) + " ***"
#            print "*** PORTS " + str(tcp_packet.srcport) + " " + \
#                str(tcp_packet.dstport) + " " + \
#                str(tcp_packet.csum) + " " + \
#                str(new_tcp.srcport) + " " + str(new_tcp.dstport) + " " + \
#                str(new_tcp.csum) + " ***"
#            pre_tcp = eth_packet.hdr('') + vlan_packet.hdr('') + ip_packet.hdr('')
#            post_tcp = new_tcp.hdr('')
#           print "PRE = " + str(len(pre_tcp)) + " " + str(len(post_tcp))

            ip_head_len = ip_packet.iplen - len(ip_packet.payload)
            ip_packet_header = ip_packet.raw[:ip_head_len]
            pre_tcp = eth_packet.hdr('') + vlan_packet.hdr('') + ip_packet_header
            new_data = pre_tcp + new_tcp_data
            new_ofp = of.ofp_packet_in(xid=ofp.xid, buffer_id = None, \
                                           reason = ofp.reason, \
                                           data = new_data, in_port = ofp.in_port)
#            orig_event = event
            event = PacketIn(self._connection, new_ofp)


            # print "LEN = " + str(len(new_data)) + " " + str(len(data))
            # print "CSUM = " + str(tcp_packet.csum) + " " + str(new_tcp.csum)
            # print "OFFSET = " + str(tcp_packet.off) + " " + str(new_tcp.off)
            # print "RESERVE = " + str(tcp_packet.res) + " " + str(new_tcp.res)
            # print "OPTiONS = " + str(tcp_packet.options) + " " + str(new_tcp.options)
            
            # print "FLAGS = " + str(tcp_packet.flags) + " " + str(new_tcp.flags)

            # for opt in tcp_packet.options: print "OLD:    " + str(opt)
            # for opt in new_tcp.options: print "NEW:    " + str(opt)
            # print "TCPLENS = " + str(tcp_packet.tcplen) + " " + str(new_tcp.tcplen)
            # print data
            # print new_data


#            pdb.set_trace()

            # print str(eth_packet)
            # new_eth_packet = ethernet(new_data[:ethernet.MIN_LEN])
            # print str(new_eth_packet)

            # print str(vlan_packet)
            # new_vlan_packet = vlan(new_data[ethernet.MIN_LEN:])
            # print str(new_vlan_packet)

            # print str(ip_packet)
            # print str(ip_packet.srcip) + " " + str(ip_packet.dstip) + " " + str(ip_packet.iplen)
            # new_ip_packet = ipv4(new_data[ethernet.MIN_LEN+vlan.MIN_LEN:])
            # print str(new_ip_packet.srcip) + " " + str(new_ip_packet.dstip) + "  "  + str(new_ip_packet.iplen)
            # print str(new_ip_packet)

            # print str(tcp_packet)
            # print str(new_tcp)
            # for i in range(len(data)):
            #     if data[i] != new_data[i]:
            #         print str(i) + ": " + data[i] + " " + new_data[i]


            # *** TEST ***
#            new_ofp = of.ofp_packet_in(xid=ofp.xid, buffer_id = None, \
#                                           reason = ofp.reason, \
#                                           data = data, in_port = ofp.in_port)
#            event = PacketIn(self._connection, new_ofp)

        SimpleLearningSwitch._handle_PacketIn(self, event)


    # This test changes just tests the SimpleLearningSwitch
    def _handle_PacketIn_simple(self, event):
        SimpleLearningSwitch._handle_PacketIn(self, event)

    # This test case changes the destination port of TCP packets from 5000 to 5001
    # It is up to VMOC to make sure that the VLAN is added onto the match clause
    def _handle_PacketIn_portmod(self, event):
        data, eth_packet, vlan_packet, ip_packet, tcp_packet = self.parsePacket(event)
#        print "*** " + str(eth_packet) + " " + str(vlan_packet) + " " + str(ip_packet)

        # Switch the request over to 5001
        if tcp_packet and tcp_packet.dstport == 5000:
            match_clause = of.ofp_match.from_packet(eth_packet, event.port)
            
            dst_mac = eth_packet.dst
            out_port = self.lookup_port_for_mac(dst_mac)
            if out_port:
                set_dst_action_clause = of.ofp_action_tp_port.set_dst(5001);
                output_action_clause = of.ofp_action_output(port=out_port)
                action_clauses = [set_dst_action_clause, output_action_clause]
                msg = of.ofp_flow_mod(match=match_clause, actions=action_clauses)
                self._connection.send(msg)

        # Switch to response back to 5000
        elif tcp_packet and tcp_packet.srcport == 5001:
            match_clause = of.ofp_match.from_packet(eth_packet, event.port)

            dst_mac = eth_packet.dst
            out_port = self.lookup_port_for_mac(dst_mac)
            if out_port:
                set_dst_action_clause = of.ofp_action_tp_port.set_src(5000);
                output_action_clause = of.ofp_action_output(port=out_port)
                action_clauses = [set_dst_action_clause, output_action_clause]
                msg = of.ofp_flow_mod(match=match_clause, actions=action_clauses)
                self._connection.send(msg)

        # Oherwise (not part of this test), handle the packet as is
        else: 
            SimpleLearningSwitch._handle_PacketIn(self, event)

    # This test case creates flow mods for other VLAN's.
    # Should get filtered out by VMOC
    def _handle_PacketIn_bad(self, event):
        data, eth_packet, vlan_packet, ip_packet, tcp_packet = self.parsePacket(event)

        if vlan_packet.type == ethernet.IP_TYPE:

            match_clause = of.ofp_match.from_packet(eth_packet, event.port)
            match_clause.dl_vlan = 999
            
            action_clause = of.ofp_action_output()
            action_clause.port = 100
            msg = of.ofp_flow_mod(match=match_clause, action=action_clause)
            self._connection.send(msg)

        # In addition, handle the packet as is
        SimpleLearningSwitch._handle_PacketIn(self, event)

    # This case creates packet out actions with no VLAN tag
    # VMOC should put them on
    def _handle_PacketIn_stripped(self, event):

        data, eth_packet, vlan_packet, ip_packet, tcp_packet = self.parsePacket(event)

        if vlan_packet.type == ethernet.IP_TYPE:

            # Grab the ethernet part of the header
            new_eth_packet = ethernet(eth_packet.raw)
            new_eth_packet.type = vlan_packet.type
            E = new_eth_packet.hdr('')
            R = new_eth_packet.raw[IP_START:]
            stripped_data = E + R
            msg = of.ofp_packet_out(data=stripped_data)
            self._connection.send(msg)

        # In addition, handle the packet as is
        SimpleLearningSwitch._handle_PacketIn(self, event)
        

    # Return data, ethernet packet, vlan_packet and 
    # IP or ARP packet for packet event
    def parsePacket(self, event):

        # 
        data = event.ofp.data
        ethernet_packet = ethernet(raw=data)
#        print str(ethernet_packet)
        if ethernet_packet.type != ethernet.VLAN_TYPE:
            log.debug("WEIRD: Got packet without VLAN")
            return data, ethernet_packet, None, None

        vlan_packet = vlan(raw=data[ethernet.MIN_LEN:])
        ethernet_packet.set_payload(vlan_packet)
#        print str(vlan_packet)

        ip_packet = None
        if vlan_packet.eth_type == ethernet.ARP_TYPE:
            ip_packet = arp(raw=data[IP_START:])
            vlan_packet.set_payload(ip_packet)
        elif vlan_packet.eth_type == ethernet.IP_TYPE:
            ip_packet = ipv4(raw=data[IP_START:])
            vlan_packet.set_payload(ip_packet)
        elif vlan_packet.eth_type == ethernet.IPV6_TYPE:
            pass
        else:
            log.debug("GOT soemthing that wasn't expecting: " + vlan_packet.eth_type)

        tcp_packet = None
        if ip_packet and vlan_packet.eth_type == ethernet.IP_TYPE:
            if ip_packet.protocol == ipv4.TCP_PROTOCOL:
                tcp_raw = ip_packet.raw[ipv4.MIN_LEN:]
                tcp_packet = tcp(raw=tcp_raw)
                ip_packet.set_payload(tcp_packet)
                payload = tcp_packet.payload
#                print "TCP = " + str(tcp_packet) + " PAYLOAD = " + payload
#            print str(ip_packet)
#            ip_packet.dump()
        return data, ethernet_packet, vlan_packet, ip_packet, tcp_packet

class VMOCTest(object):
    def __init__(self, test_mode):
        core.openflow.addListeners(self)
        self._test_mode = test_mode

    def _handle_ConnectionUp(self, event):
        log.debug("Connection %s" % (event.connection,))
        VMOCTestController(event.connection, self._test_mode)


def launch(test_mode='asterisk'):
    log.debug("VMOCTestController.launch: " + test_mode);
    core.registerNew(VMOCTest, test_mode)

