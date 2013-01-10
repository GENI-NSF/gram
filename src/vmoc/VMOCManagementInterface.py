# Server that presents a management interface to add/remove/query controllers

import pdb
from pox.core import core
import socket
import sys
import SocketServer
import threading
import pox.openflow.libopenflow_01 as of
from ControllerRegistry import ControllerRegistry
import VMOCSwitchControllerMap as scmap
from VMOCControllerConnection import VMOCControllerConnection

# Single instance managed by this server
controller_registry = ControllerRegistry()

log = core.getLogger() # Use central logging service

class VMOCManagementServerHandler(SocketServer.BaseRequestHandler):

	# Commands:
	# register url vlan,mac,mac vlan,mac,mac
	# unregister url
	# dump
	def parseCommand(self, command_line):
		pieces = command_line.split();
		command = pieces[0]
		url = None
		macs_for_vlans = dict()
		if len(pieces) > 1:
			url = pieces[1]
		if len(pieces) > 2:
			for i in range(2, len(pieces)):
				vlan_macs_raw = pieces[i]
				vlan_macs = vlan_macs_raw.split(",")
				macs_for_vlans[vlan_macs[0]] = vlan_macs[1:]
		return command, url, macs_for_vlans

	def handle(self):
		data = self.request.recv(1024).strip()
		log.debug("Received " + data)
		command, controller_url, macs_for_vlans = \
		    self.parseCommand(data)
		response = ""
		try:
			if command == "register":
				response = "Registered controller : " + \
				    controller_url + " " + str(macs_for_vlans)
				controller_registry.register(\
					controller_url, \
						macs_for_vlans)
				scmap.add_controller_connection(\
					controller_url, True)
#				scmap.dump_switch_controller_map()
			elif command == "unregister":
				response = "Unregistered controller : " + \
				    controller_url
				controller_registry.unregister(controller_url)
				remove_controller_connection(controller_url)
			elif command == "dump":
				response = controller_registry.dump();
			else:
				response = "Illegal command "  + command
		except AssertionError, error:
			response = str(error)
		self.request.sendall(response)

class VMOCManagementInterface(threading.Thread):
 	def __init__(self, port):
 		threading.Thread.__init__(self)
 		self._host, self._port = '', port

 	def run(self):
 		server = \
		    SocketServer.TCPServer((self._host, self._port), \
						   VMOCManagementServerHandler)
 		try:
 			server.serve_forever()
 		except BaseException:
 			server.shutdown()
 		log.info("VMOCMI.exit")

# Some global functions to lookup registered information 
# from the controller registry

def get_all_registered_controller_urls():
	return controller_registry._registry.keys()

def lookup_controller_info_by_url(url):
	return controller_registry.lookup_by_url(url)


def lookup_controller_info_by_vlan(vlan):
	return controller_registry.lookup_by_vlan(vlan)
