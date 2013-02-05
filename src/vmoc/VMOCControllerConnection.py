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

# Handle the client connection between the VMOC and 
# each registered controller for each switch

import inspect
import select
import socket
import threading
import pdb
from pox.core import core
from pox.lib.util import makePinger
from pox.lib.packet.ethernet import ethernet
from pox.lib.addresses import EthAddr
from pox.lib.packet.vlan import vlan
from pox.openflow.util import make_type_to_class_table
from pox.openflow.libopenflow_01 import *
from pox.openflow import libopenflow_01 as of
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.vlan import vlan
import VMOCSwitchControllerMap as scmap
from VMOCSliceRegistry import slice_registry_lookup_slices_by_url, slice_registry_dump
from VMOCUtils import *
import gram.am.gram.config as config


log = core.getLogger() # Use central logging service

# Thread to manage connection with a controller:
# Listen to and process all messages received asynchronously from controller
class VMOCControllerConnection(threading.Thread):


    def __init__(self, url, switch_connection, vlan, open_on_create=True):
        threading.Thread.__init__(self)
        self._running = False
        self._vlan = int(vlan)

        self.ofp_msgs = make_type_to_class_table()
        self.ofp_handlers = {
            # Reactive handlers
            ofp_type_rev_map['OFPT_HELLO'] : self._receive_hello,
            ofp_type_rev_map['OFPT_ECHO_REQUEST'] : self._receive_echo,
            ofp_type_rev_map['OFPT_FEATURES_REQUEST'] : \
                self._receive_features_request,
            ofp_type_rev_map['OFPT_FLOW_MOD'] : self._receive_flow_mod,
            ofp_type_rev_map['OFPT_PACKET_OUT'] : self._receive_packet_out,
            ofp_type_rev_map['OFPT_BARRIER_REQUEST'] : \
                self._receive_barrier_request,
            ofp_type_rev_map['OFPT_GET_CONFIG_REQUEST'] : \
                self._receive_get_config_request,
            ofp_type_rev_map['OFPT_SET_CONFIG'] : self._receive_set_config,
            ofp_type_rev_map['OFPT_STATS_REQUEST'] : \
                self._receive_stats_request,
            ofp_type_rev_map['OFPT_VENDOR'] : self._receive_vendor,
            # Proactive responses
            ofp_type_rev_map['OFPT_ECHO_REPLY'] : self._receive_echo_reply
            # TODO: many more packet types to process
            }


        self._switch_connection = switch_connection
        if  not hasattr(switch_connection, '_dpid'): pdb.set_trace()

        # The controller sees VMOC as a switch. And we want each
        # connection to a controller to have a different DPID (or controllers
        # get confused). So VMOC has a different connection to a controller
        # by VLAN. And a controller may connect to multiple VMOCs.
        # So we need to construct a DPID that is unique over the space
        # of VLAN and switch_DPID.
        #
        # Here's what we do.
        # DPID's are 64 bits, of which the lower 48 are MAC addresses
        # and the top 16 are 'implementer defined' (Openflow spec).
        # The MAC should be unique and (for the contoller to talk to VMOC
        # we don't need to maintain the switch implementation features.
        # The vlan is 3 hex digits or 12 bits. 
        # So we take the VLAN and put it at the top three hex bytes of
        # the switch's DPID to form the VMOC-Controller-VLAN-specific DPIC
        #
        # VLAN in top 3 hex chars
        # Switch DPID in lower 13 hex chars
        controller_connection_dpid = \
            ((self._vlan & 0xfff) << 48) + \
            (switch_connection._dpid & 0x000fffffffffffff)  
        self._dpid = controller_connection_dpid

        self._url = url
        (host, port) = VMOCControllerConnection.parseURL(url)
        self._host = host;
        self._port = port
        self._sock = None

        # Make it optional to not open on create (for debugging at least)
        if open_on_create:
            self.open()

    def open(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((self._host, self._port))
        self.start()
        # When we have a new controller, send it a 'hello' (acting like
        # we are a switch to whom they are talking
        hello_msg = of.ofp_hello()
        self.send(hello_msg)

    def close(self):
#        print "CLOSING " + str(self)
        self._sock.close()
#        print "SOCKET CLOSED " + str(self)
        self._running = False
#        print "RUNNING = FALSE " + str(self)

    def __str__(self):
        return "[VMOCControllerConnection DPID %s URL %s VLAN %d]" % (self._dpid, self._url, self._vlan)

    def getURL(self):
        return self._url

    def getVLAN(self):
        return self._vlan

    def getSwitchConnection(self):
        return self._switch_connection

    def _receive_hello(self, ofp):
        log.debug("CC " + self._url + " recvd " + "'OFPT_HELLO")
#        log.debug("CC " +  str(ofp))

    def _receive_echo(self, ofp):
        log.debug("CC " + self._url + " recvd " + "'OFPT_ECHO_REQUEST")
#        log.debug("CC " +  str(ofp))
        echo_reply = ofp_echo_reply(xid=ofp.xid)
        self.send(echo_reply)

    def _receive_features_request(self, ofp):
        log.debug("CC " + self._url + " recvd " + "'OFPT_FEATURES_REQUEST")
#        log.debug("CC " +  str(ofp))
        switch = scmap.lookup_switch_for_controller_connection(self)
        features_reply = switch._features_reply
#        print "Features Request " + str(ofp.xid) + " " + str(features_reply.xid)
        features_reply.xid = ofp.xid
        self.send(features_reply)

    def _receive_flow_mod(self, ofp):
        log.debug("CC " + self._url + " recvd " + "'OFPT_FLOW_MOD")
#        log.debug("CC " +  str(ofp))
        # Need to forward this back to the switch
        self.forwardToAllAppropriateSwitches(ofp)

    def _receive_packet_out(self, ofp):
        log.debug("CC " + self._url + " recvd " + "'OFPT_PACKET_OUT")
        self.forwardToAllAppropriateSwitches(ofp)
#        log.debug("CC " +  str(ofp))

    def _receive_barrier_request(self, ofp):
        log.debug("CC " + self._url + " recvd " + "'OFPT_BARRIER_REQUEST")
#        log.debug("CC " +  str(ofp))
#        print "BARRIER ID " + str(ofp.xid)
        barrier_reply = ofp_barrier_reply(xid = ofp.xid)
#        print "BARRIER_REPLY = " + str(barrier_reply)
#        print "BARRIER_REQUEST = " + str(ofp)
        self.send(barrier_reply)

    def _receive_get_config_request(self, ofp):
        log.debug("CC " + self._url + " recvd " + \
                      "'OFPT_GET_CONFIG_REQUEST" + str(ofp))
#        log.debug("CC " + self._url + " recvd " + "'OFPT_GET_CONFIG_REQUEST ")

    def _receive_set_config(self, ofp):
        log.debug("CC " + self._url + " recvd " + "'OFPT_SET_CONFIG")
#        log.debug("CC " + str(ofp))

    def _receive_stats_request(self, ofp):
        log.debug("CC " + self._url + " recvd " + "'OFPT_STATS_REQUEST")
#        log.debug("CC " +  str(ofp))

    def _receive_vendor(self, ofp):
        log.debug("CC " + self._url + " recvd " + "'OFPT_VENDOR")
#        log.debug("CC " +  str(ofp))

    def _receive_echo_reply(self, ofp):
        log.debug("CC " + self._url + " recvd " + "'OFPT_ECHO_REPLY")
#        log.debug("CC " +  str(ofp))

    # For now, forward the ofp to all switches assocaited with VMOC
    def forwardToAllAppropriateSwitches(self, ofp):

#        print "Forwarding to switch : " + str(ofp)

        # Send any message back to switch EXCEPT
        #     RECEIVE_FLOW_MOD : Need to add on VLAN tag, DROP if VLAN isn't consistent with slice
        #                      : DROP if SRC and DST isn't consistent with slice
        #     RECEIVE_PACKET_OUT : Need to make sure it has VLAN tag and has MACs on that VLAN

        # Get switch for this connection
        switch = scmap.lookup_switch_for_controller_connection(self)

        ofp_revised = self.validateMessage(ofp, switch)
        if ofp_revised is None:
            log.debug("Not forwarding controller message to switch " + 
                      str(type(ofp)) + str(switch))
        else:
            log.debug("Forwarding controller message to switch " + \
                          str(type(ofp)) + " " + str(switch))
            switch.send(ofp_revised)

    # Determine if message should be forwarded to switch
    # If it is a flow mod:
    #    - If the match has a vlan tag, make sure it fits the connection's VLAN (else drop)
    #    - If the match has no VLAN tag, add it in
    #    - If the action has aset-vlan or strip-vlan,drop it
    # If it is a packet:
    #    - If it has a VLAN, make sure it fits in connection's VLAN (else drop)
    #    - If it doesn't have a VLAN, add the VLAN of the connection to the packet
    def validateMessage(self, ofp, switch):

        ofp_revised = None
        if ofp.header_type == of.OFPT_FLOW_MOD:

            # Need to narrow down between the sub-cases for FLOW MOD below
            # Check that the match is okay
            match = ofp.match
            
#           print "COMMAND = " + str(ofp.command) + " " + str(of.OFPFC_DELETE)
#            print "WC = " + str(match.wildcards) + " " + str(OFPFW_ALL)
            if ofp.command == of.OFPFC_DELETE and not match.dl_vlan:
                if not config.vmoc_accept_clear_all_flows_on_startup:
                    return None
                # Weird case of getting a 'clear all entries' at startup
#                print "OFP = " + str(ofp)
#                print "*** CASE 0 ***"
                return ofp
            elif match.dl_vlan == of.OFP_VLAN_NONE or not match.dl_vlan:
                if not config.vmoc_set_vlan_on_untagged_flow_mod:
                    return ofp
                # add in the tag to the match if not set
#                print "OFP = " + str(ofp)
#                print "MATCH = " + str(match)
                match.dl_vlan = self._vlan
#                print "MATCH = " + str(match)
#                print "MATCH.DL_VLAN = " + str(match.dl_vlan) + " " + str(of.OFP_VLAN_NONE)
#               print "*** CASE 1 ***"
#               
#               pdb.set_trace()
                return ofp 

            elif match.dl_vlan != self._vlan:
                return ofp # ***
                log.debug("Dropping FLOW MOD: match tagged with wrong VLAN : " + \
                              str(ofp) + " " + str(self))
#                print "*** CASE 2 ***"
#               pdb.set_trace()
                return None

            # Check that the actions are okay
            actions = ofp.actions
            for action in actions:
                if isinstance(action, ofp_action_vlan_vid) and action.vlan_vid != self._vlan:
                    log.debug("Dropping FLOW MOD: action to set wrong VLAN : " + \
                              str(ofp) + " " + str(self))
#                    print "*** CASE 3 ***"
#                    pdb.set_trace()
                    return None

            return ofp

        elif ofp.header_type == of.OFPT_PACKET_OUT:

            data = ofp.data
            ethernet_packet = ethernet(raw=data)
            # if packet has a VLAN, make sure it fits this connection
            if ethernet_packet.type == ethernet.VLAN_TYPE:
                vlan_packet = vlan(data[ethernet.MIN_LEN:])
                if  vlan_packet.id != self._vlan:
                    log.debug("Dropping PACKET OUT: wrong VLAN set : "  + 
                              str(vlan_packet) + " " + str(ofp) + " " + str(self))
#                    print "*** CASE 4 ***"
#                   pdb.set_trace()
                    return None
                else:
                    return ofp
            else: 
                if not config.vmoc_set_vlan_on_untagged_packet_out:
                    return ofp 
                # If not, set it
                orig_in_port = ofp.in_port
                new_ethernet_packet = add_vlan_to_packet(ethernet_packet, self._vlan)
                # Create a new ofp from the new data
                ofp_orig = ofp
                ofp = of.ofp_packet_out(data=new_ethernet_packet.raw)
                ofp.buffer_id = None
                ofp.in_port = orig_in_port
                ofp.actions = ofp_orig.actions
                ofp.xid = ofp_orig.xid
                log.debug("Adding vlan to PACKET_OUT : " +  \
                              str(ethernet_packet) + " " + str(new_ethernet_packet) + " " + \
                              str(ofp) + " " + str(self))
#                print str(ethernet_packet)
#                ip_packet = ipv4(ethernet_packet.raw[ethernet.MIN_LEN:])
#                print str(ip_packet)
#                print str(ofp_orig)
#                print str(ofp)
#                print str(new_ethernet_packet)
#                vlan_packet = vlan(new_ethernet_packet.raw[ethernet.MIN_LEN:])
#                print str(vlan_packet)
#                ip_packet = ipv4(new_ethernet_packet.raw[ethernet.MIN_LEN+vlan.MIN_LEN:])
#                print str(ip_packet)
#                pdb.set_trace()
                return ofp

        else:  # Not a FLOW_MOD or PACKET_OUT
            return ofp

    # Determine if this vlan/src/dest tuple is valid for the slice
    # managed by this controller
    def belongsToSlice(self, vlan_id, src, dst):
        return vlan_id == self._vlan

#         slice_configs = slice_registry_lookup_slices_by_url(self._url)

# #        slice_registry_dump(True)

#         belongs = False
#         for slice_config in slice_configs:
#             if slice_config.belongsToSlice(vlan_id, src, dst): 
#                 belongs = True
#                 break
#         print "Belongs (Controller) = " + str(self) + " " + str(belongs) + " " + \
#             str(vlan_id) + " " + str(src) + " " + str(dst)
#         return belongs
        
    # Parse URL of form http://host:port
    @staticmethod
    def parseURL(url):
        pieces = url.replace("/", "").split(':');
        host = pieces[1]
        port = int(pieces[2])
        return host, port

    def run(self):

        _select_timeout = 5
        _buf_size = 8192

        self._running = True

        buf = b''
        buf_empty = True

        while self._running:

#            print "VMOCControllerConnection Loop " + \
#                 str(len(buf)) + " " + str(buf_empty)

            # If there is no more message data in the buffer, read from socket
            # blocking within this thread
            if buf_empty:
#                print "BEFORE SELECT " + str(self._sock)
                input_ready, output_ready, except_ready = \
                    select.select([self._sock], [], [], _select_timeout)
#                print "AFTER SELECT " + str(self._sock) + " " + str(len(input_ready))
                if not input_ready:
                    continue

                new_buf = ''
                try:
                    new_buf = self._sock.recv(_buf_size)
                except:
                    # if we get an empty buffer or exception, kill connection
                    pass 
#                print "AFTER RECV " + str(self._sock)
                if len(new_buf) == 0:
                    self._sock.close()
                    self._running = False;
                    break
                else:
                    buf = buf + new_buf

#            log.debug("Received buffer : " + str(len(buf)))
            if ord(buf[0]) != of.OFP_VERSION:
                log.warning("Bad OpenFlow version (" + str(ord(buf[0])) +
                            ") on connection " + str(self))
                return 
            # OpenFlow parsing occurs here:
            ofp_type = ord(buf[1])
            packet_length = ord(buf[2]) << 8 | ord(buf[3])
            buf_empty = packet_length > len(buf)

#            log.debug("Parsed " + str(ofp_type) + " " + \
#                          str(packet_length) + " " + \
#                          str(len(buf)) + " " + str(buf_empty))

            if not buf_empty:
                msg_obj = self.ofp_msgs[ofp_type]()
                msg_obj.unpack(buf)
#                log.debug("Received msg " + str(ofp_type) + " " + \
#                          str(packet_length) + \
#                          str(type(msg_obj)))
                buf = buf[packet_length:]
                # need to at least have the packet_length
                buf_empty = len(buf) < 4 

                try:
                    if ofp_type not in self.ofp_handlers:
                        msg = "No handler for ofp_type %s(%d)" % \
                            (ofp_type_map.get(ofp_type), ofp_type)
                        raise RuntimeError(msg)
                    h = self.ofp_handlers[ofp_type]
#                    print "Calling " + str(h) + " on msg " + str(msg_obj) + " " + str(msg_obj.xid)
                    if "connection" in inspect.getargspec(h)[0]:
                        h(msg_obj, connection=self)
                    else:
                        h(msg_obj)

                except Exception as e:
#                    print "Exception " + str(e)
                    log.exception(e)
                    self._running = False

        scmap.remove_controller_connection(self)
        # If the controller connection died, we should try to restart 
        # it if or when the controller comes back
        scmap.create_controller_connection(self._url, self._vlan)

        log.debug("Exiting VMCControllerConnection.run")



    # To be called synchronously when VMOC determines it should
    # Send a message to this client
    def send(self, message):
        log.debug("Sending to client: " + self._url + " " + str(type(message)))
        data = message.pack()
        bytes_sent = self._sock.send(data)
#        log.debug("Sent " + str(bytes_sent) + " bytes")






        

