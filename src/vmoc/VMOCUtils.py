# Set of utilities for helping with VMOC functionailty and testing

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.openflow import *
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.vlan import vlan
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.arp import arp
from pox.lib.packet.tcp import tcp
from pox.lib.addresses import *

log = core.getLogger()

# Send an OF command to flood a packet out a connection
def flood_packet(event, connection):
    log.debug("Flooding " + str(event))
    msg = of.ofp_packet_out()
    msg.data = event.ofp
    msg.in_port = event.port
    msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
    connection.send(msg)

# Send an OF command to install a flow-mod to send packets 
# matching given packet out given port
def send_flowmod_for_packet(event, connection, packet, out_port):
    msg = of.ofp_flow_mod()
    msg.match = of.ofp_match.from_packet(packet, event.port)
    msg.idle_timeout = 10
    msg.hard_timeout = 30
    msg.actions.append(of.ofp_action_output(port=out_port))
    connection.send(msg)
    log.debug("Setting flow mod " + str(msg))

# Send an OF command to send a packet out a given port
def send_packet_out(connection, buffer_id, raw_data, in_port, out_port):
    msg = of.ofp_packet_out()
    if  buffer_id is not None and buffer_id != -1:
        msg.buffer_id = buffer_id
    else:
        # IN : We get 
        # WARN|unexpected flow from datapath in_port(2),eth(src=fa:16:3e:60:0b:ee,dst=fa:16:3e:3d:e2:0a),eth_type(0x8100),vlan(vid=1003,pcp=0),encap(eth_type(0x0800),ipv4(src=10.0.174.100,dst=10.0.174.101,proto=6,tos=0,ttl=64,frag=no),tcp(src=41536,dst=5000))
        # OUT : We get nothing (no error but no transmission)
        #
        in_port = of.OFPP_NONE
        if raw_data is None: return
        msg.data = raw_data
        msg.buffer_id = None

    print "SPO : " + str(buffer_id) + " " + str(in_port) + " " + str(of.OFPP_NONE) + " " + str(out_port)
    msg.in_port = in_port

    action = of.ofp_action_output(port=out_port)
    msg.actions.append(action)
    log.debug("Sending packet_out " + str(msg))
    msg.show()
    result = connection.send(msg)
    print "SPO.result = " + str(result)

# Create a new ethernet packet with vlan tag fields added
def add_vlan_to_packet(ethernet_packet, vlan_id):
    # Grab the ethernet packet = E
    new_ethernet_packet = ethernet(ethernet_packet.raw)
    new_ethernet_packet.type = ethernet.VLAN_TYPE
    E = new_ethernet_packet.hdr('')
    # Create the vlan packet = V
    vlan_packet = vlan()
    vlan_packet.id = vlan_id
    vlan_packet.pcp = 0
    vlan_packet.eth_type = ethernet_packet.type
    V = vlan_packet.hdr('')
    # Grab the rest of the packet = R
    R = ethernet_packet.raw[ethernet.MIN_LEN:]
    # Construct E + V + R
    new_raw = E + V + R
    new_ethernet_packet = ethernet(new_raw)
    return new_ethernet_packet

                  
if __name__ == "__main__":
    eth = ethernet()
    eth.dst = EthAddr("01:02:03:04:05:06")
    eth.src = EthAddr("11:12:13:14:15:16")
    eth.type = ethernet.IP_TYPE
    ip = ipv4()
    ip.srcip = IPAddr("128.99.98.97")
    ip.dstip = IPAddr("128.89.8.87")

    joint_eth = ethernet(eth.hdr('') + ip.hdr(''))
    print "JOINT = " + str(joint_eth)
    print "IP = " + str(ipv4(joint_eth.raw[ethernet.MIN_LEN:]))
    joint_eth_vlan = add_vlan_to_packet(joint_eth, 1000)
    print "JOINT_V = " + str(joint_eth_vlan)
    print "V = " + str(vlan(joint_eth_vlan.raw[ethernet.MIN_LEN:]))
    print "IP = " + str(ipv4(joint_eth_vlan.raw[ethernet.MIN_LEN+vlan.MIN_LEN:]))

    
