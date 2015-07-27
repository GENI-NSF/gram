# Copyright 2011 James McCauley
#
# This file is part of POX.
#
# POX is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# POX is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with POX.  If not, see <http://www.gnu.org/licenses/>.

"""
A simple L2 learning switch.

Modified from POX l2_learning to send a single flow_mod
that matches on DST_MAC and takes action to send to associated port
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.packet.vlan import vlan
from pox.lib.util import dpid_to_str
from pox.lib.util import str_to_bool
import time
import gram.am.gram.config as config

log = core.getLogger()

# We don't want to flood immediately when a switch connects.
FLOOD_DELAY = 5

class L2SimpleLearningSwitch (object):
  """
  The learning switch "brain" associated with a single OpenFlow switch.

  When we see a packet, we'd like to output it on a port which will
  eventually lead to the destination.  To accomplish this, we build a
  table that maps addresses to ports.

  We populate the table by observing traffic.  When we see a packet
  from some source coming from some port, we know that source is out
  that port.

  When we want to forward traffic, we look up the desintation in our
  table.  If we don't know the port, we simply send the message out
  all ports except the one it came in on.  (In the presence of loops,
  this is bad!).

  In short, our algorithm looks like this:

  For each packet from the switch:
  1) Use source address and switch port to update address/port table
  2) Is transparent = False and either Ethertype is LLDP or the packet's
     destination address is a Bridge Filtered address?
     Yes:
        2a) Drop packet -- don't forward link-local traffic (LLDP, 802.1x)
            DONE
  3) Is destination multicast?
     Yes:
        3a) Flood the packet
            DONE
  4) Port for destination address in our address/port table?
     No:
        4a) Flood the packet
            DONE
  5) Is output port the same as input port?
     Yes:
        5a) Drop packet and similar ones for a while
  6) Install flow table entry in the switch so that this
     flow goes out the appopriate port
     *** This is the part of l2_learning we are changing ***
     6a) Send the packet out appropriate port
  """
  def __init__ (self, connection, transparent):
    # Switch we'll be adding L2 learning switch capabilities to
    self.connection = connection
    self.transparent = transparent

    # Our table
    self.macToPort = {}

    # We want to hear PacketIn messages, so we listen
    # to the connection
    connection.addListeners(self)

    # We just use this to know when to log a helpful message
    self.hold_down_expired = False

    #log.debug("Initializing LearningSwitch, transparent=%s",
    #          str(self.transparent))

  def _handle_PacketIn (self, event):
    """
    Handle packet in messages from the switch to implement above algorithm.
    """

    packet = event.parsed

    def flood (message = None):
      """ Floods the packet """
      msg = of.ofp_packet_out()
      if time.time() - self.connection.connect_time > FLOOD_DELAY:
        # Only flood if we've been connected for a little while...

        if self.hold_down_expired is False:
          # Oh yes it is!
          self.hold_down_expired = True
          log.info("%s: Flood hold-down expired -- flooding",
              dpid_to_str(event.dpid))

        if message is not None: log.debug(message)
        #log.debug("%i: flood %s -> %s", event.dpid,packet.src,packet.dst)
        msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
      else:
        pass
        #log.info("Holding down flood for %s", dpid_to_str(event.dpid))
      msg.data = event.ofp
      msg.in_port = event.port
      self.connection.send(msg)

    def drop (duration = None):
      """
      Drops this packet and optionally installs a flow to continue
      dropping similar ones for a while
      """
      if duration is not None:
        if not isinstance(duration, tuple):
          duration = (duration,duration)
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet)
        msg.idle_timeout = duration[0]
        msg.hard_timeout = duration[1]
        msg.buffer_id = event.ofp.buffer_id
        log.info("Dropping (1)" + event.of.buffer_id)
        self.connection.send(msg)
      elif event.ofp.buffer_id is not None:
        msg = of.ofp_packet_out()
        msg.buffer_id = event.ofp.buffer_id
        msg.in_port = event.port
        log.info("Dropping (2)" + event.of.buffer_id)
        self.connection.send(msg)

    self.macToPort[packet.src] = event.port # 1

    if not self.transparent: # 2
      if packet.type == packet.LLDP_TYPE or packet.dst.isBridgeFiltered():
        drop() # 2a
        return

    if packet.dst.is_multicast:
      flood() # 3a
    elif packet.dst not in self.macToPort: # 4
      flood("Port for %s unknown -- flooding" % (packet.dst,)) # 4a
    else:
      port = self.macToPort[packet.dst]
      if port == event.port: # 5
        # 5a
        log.warning("Same port for packet from %s -> %s on %s.%s.  Drop."
                    % (packet.src, packet.dst, dpid_to_str(event.dpid), port))
        drop(10)
        return

      # 6
      # Install the flow and send the packet out
      log.debug("installing flow for %s.%d -> %s.%d" %
                (packet.src, event.port, packet.dst, port))

      # This is the change from the POX release l2_learning
      # Only match on the dst MAC
      msg = of.ofp_flow_mod()
      msg.out_port = of.OFPP_NONE

      # Use this line for the HP switch and comment out the next for
      if(config.switch_type == 'HP'):
        msg.match = of.ofp_match.from_packet(packet, event.port)
      else:
        # These 3 lines of code work for the DELL switch
        msg.match = of.ofp_match()
        msg.match.dl_src = packet.src
        msg.match.dl_dst = packet.dst

      p = packet.next
      if isinstance(p, vlan):
        msg.match.dl_vlan = p.id
        msg.match.dl_vlan_pcp = p.pcp
#          log.debug("Matching on VLAN " + str(p))

      msg.idle_timeout = 0
      msg.hard_timeout = 0
      msg.actions.append(of.ofp_action_output(port = port))
#        msg.data = event.ofp # 6a

#        log.debug("MSG = " + str(msg))
      self.connection.send(msg)


class l2_simple_learning (object):
  """
  Waits for OpenFlow switches to connect and makes them learning switches.
  """
  def __init__ (self, transparent):
    core.openflow.addListeners(self)
    self.transparent = transparent

  def _handle_ConnectionUp (self, event):
    log.debug("Connection %s" % (event.connection,))
    L2SimpleLearningSwitch(event.connection, self.transparent)


def launch (transparent=False):
  """
  Starts an L2 learning switch.
  """
  core.registerNew(l2_simple_learning, str_to_bool(transparent))
