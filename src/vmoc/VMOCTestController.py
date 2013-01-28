# A test controller for 1-30-2013 demonstration of
# Gram/VMOC managing experimenter controllers

# First, there are tests that don't involve this controller
# 1- No controller (no VMOC)
# 2- Slice not regisgtered with VMOC
# 2- Slice but null Controller  (use default)

# Then there are several test 'modes' provided by this controller
# 'asterisk' - Turn all characters in header into '*'
# 'bounce' - Turn the IP dst to the IP src of all traffic
# 'bad' - Generate flow mods and packets not within your VLAN


from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.openflow import *
from pox.lib.util import dpid_to_str
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
        elif self._test_mode == 'bounce':
            self._handle_PacketIn_bounce(event)
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
#        print "*** " + str(eth_packet) + " " + str(vlan_packet) + " " + str(ip_packet)

        if tcp_packet:
            payload = tcp_packet.payload
            combined_header = data[:TCP_PAYLOAD_START]
            new_payload = payload.translate(self._transtable)
#            print "*** TCP " + payload + " " + new_payload + " ***"
            new_data = combined_header + new_payload
            new_ofp = ofp_packet_in(xid=ofp.xid, buffer_id = None, reason = ofp.reason, \
                                        data = new_data, in_port = ofp.in_port)
            event = PacketIn(self.connection, new_ofp)

        SimpleLearningSwitch._handle_PacketIn(self, event)


    # This test case changes the destination of any IP packet into its source
    # When you get an IP packet from A to B, write a flow-mod that says
    #   Match: src_ip=A, Action : dst_ip=A
    # It is up to VMOC to make sure that the VLAN is added onto the match clause
    def _handle_PacketIn_bounce(self, event):
        data, eth_packet, vlan_packet, ip_packet, tcp_packet = self.parsePacket(event)
#        print "*** " + str(eth_packet) + " " + str(vlan_packet) + " " + str(ip_packet)

        if vlan_packet.type == ethernet.IP_TYPE:

            ip_src = ip_packet.srcip

            match_clause = of.ofp_match()
            match_clause.set_nw_src(ip_src)
            
            action_clause = of.ofp_action_nw_addr()
            action_clause.type = of.OFPAT_SET_NW_DST
            action_clause.nw_addr = ip_src
            msg = of.ofp_flow_mod(match=match_clause, action=action_clause)
            self._connection.send(msg)

        # In addition, handle the packet as is
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
        print str(ethernet_packet)
        if ethernet_packet.type != ethernet.VLAN_TYPE:
            print "WEIRD: Got packet without VLAN"
            return data, ethernet_packet, None, None

        vlan_packet = vlan(data[ethernet.MIN_LEN:])
        print str(vlan_packet)

        ip_packet = None
        if vlan_packet.eth_type == ethernet.ARP_TYPE:
            ip_packet = arp(data[IP_START:])
        elif vlan_packet.eth_type == ethernet.IP_TYPE:
            ip_packet = ipv4(data[IP_START:])
        elif vlan_packet.eth_type == ethernet.IPV6_TYPE:
            pass
        else:
            print "GOT soemthing that wasn't expecting: " + \
                vlan_packet.eth_type

        tcp_packet = None
        if ip_packet and vlan_packet.eth_type == ethernet.IP_TYPE:
            if ip_packet.protocol == ipv4.TCP_PROTOCOL:
                tcp_raw = ip_packet.raw[ipv4.MIN_LEN:]
                tcp_packet = tcp(tcp_raw)
                payload = tcp_packet.payload
#                print "TCP = " + str(tcp_packet) + " PAYLOAD = " + payload
            print str(ip_packet)
            ip_packet.dump()
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

