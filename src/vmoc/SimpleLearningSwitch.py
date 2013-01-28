from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.openflow import *

log = core.getLogger()

class SimpleLearningSwitch(object):

    def __init__(self, connection, write_flowmods):
        self._write_flowmods = write_flowmods
        self._connection = connection

        self._mac_to_port = {}

        connection.addListeners(self)

    # Simple learning switch logic
    # Remember where a given packet came from (src, port)
    # If a packet comes in with an unknwon dest, flood the packet
    def _handle_PacketIn(self, event):

        packet = event.parsed # Ethernet packet

        # Learn that this MAC comes from this port
        src_port = event.port
        src = packet.src
        dst = packet.dst

        if not self._mac_to_port.has_key(src) or self._mac_to_port[src] != src_port:
            log.debug("Learned that " + str(src) + " => " + str(src_port))
            self._mac_to_port[src] = src_port

        if not self._mac_to_port.has_key(dst):
            log.debug("Flooding " + str(event))
            self.flood(event)
        else:
            out_port = self._mac_to_port[dst]
            if self._write_flowmods:
                msg = of.ofp_flow_mod()
                msg.match = of.ofp_match.from_packet(packet, event.port)
                msg.idle_timeout = 10
                msg.hard_timeout = 30
                msg.actions.append(of.ofp_action_output(port=out_port))
                self._connection.send(msg)
                log.debug("Setting flow mod " + str(msg))

            msg = of.ofp_packet_out(data=packet.raw, in_port = src_port)
            msg.actions.append(of.ofp_action_output(port=out_port))
            self._connection.send(msg)
#            log.debug("Sending message : " + str(msg))
    
    def flood(self, event):
        msg = of.ofp_packet_out()
        msg.data = event.ofp
        msg.in_port = event.port
        msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
        self._connection.send(msg)
             
            

        
