# Handle the client connection between the VMOC and 
# each registered controller for each switch

import inspect
import select
import socket
import threading
import pdb
from pox.core import core
from pox.lib.util import makePinger
from pox.openflow.util import make_type_to_class_table
from pox.openflow.libopenflow_01 import *
from pox.openflow import libopenflow_01 as of
import VMOCSwitchControllerMap as scmap

log = core.getLogger() # Use central logging service

# Thread to manage connection with a controller:
# Listen to and process all messages received asynchronously from controller
class VMOCControllerConnection(threading.Thread):


    def __init__(self, url, switch_connection, open_on_create=True):
        threading.Thread.__init__(self)


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
        self._dpid = switch_connection._dpid
        self._url = url
        (host, port) = self.parseURL(url)
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

    def getURL(self):
        return self._url

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
        barrier_reply = ofp_barrier_reply(xid = ofp.xid)
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
        # Get switch for this connection
        switch = scmap.lookup_switch_for_controller_connection(self)
#        log.debug("Forwarding controller message to switch " + \
#                      str(type(ofp)) + " " + str(switch))
        switch.send(ofp)
        
        


    # Parse URL of form http://host:port
    def parseURL(self, url):
        pieces = url.replace("/", "").split(':');
        host = pieces[1]
        port = int(pieces[2])
        return host, port


    def run(self):

        _select_timeout = 5
        _buf_size = 8192

        running = True

        buf = b''
        buf_empty = True

        while running:

#            print "VMOCControllerConnection Loop " + \
#                 str(len(buf)) + " " + str(buf_empty)

            # If there is no more message data in the buffer, read from socket
            # blocking within this thread
            if buf_empty:
                select.select([self._sock], [], [], _select_timeout)
                new_buf = self._sock.recv(_buf_size)
                if len(new_buf) == 0:
                    self._sock.close()
                    running = False;
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
                    if "connection" in inspect.getargspec(h)[0]:
                        h(msg_obj, connection=self)
                    else:
                        h(msg_obj)

                except Exception as e:
                    print "Exception " + str(e)
                    log.exception(e)
                    running = False

        scmap.remove_controller_connection(self)
        log.debug("Exiting VMCControllerConnection.run")



    # To be called synchronously when VMOC determines it should
    # Send a message to this client
    def send(self, message):
#       log.debug("Sending to client: " + self._url + " " + str(type(message)))
        data = message.pack()
        bytes_sent = self._sock.send(data)
#        log.debug("Sent " + str(bytes_sent) + " bytes")






        

