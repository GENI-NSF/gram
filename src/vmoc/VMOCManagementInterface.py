# Server that presents a management interface to add/remove/query controllers

import json
import pdb
from pox.core import core
import socket
import sys
import SocketServer
import threading
import pox.openflow.libopenflow_01 as of
import VMOCSwitchControllerMap as scmap
from VMOCControllerConnection import VMOCControllerConnection
from VMOCConfig import VMOCSliceConfiguration
from VMOCGlobals import VMOCGlobals
from VMOCSliceRegistry import *

log = core.getLogger() # Use central logging service

class VMOCManagementServerHandler(SocketServer.BaseRequestHandler):

	# Commands:
	# register slice_config(JSON)
	# unregister slice_id
	# dump
	# Return command, controller_url, slice_config [last two could be None]
	def parseCommand(self, command_line):
		pieces=command_line.split(' ')
		command = pieces[0]
		slice_id = None
		slice_config = None
		if command == 'register':
			slice_config_json = ' '.join(pieces[1:])
			slice_config_attribs= json.loads(slice_config_json)
			slice_config = VMOCSliceConfiguration(attribs=slice_config_attribs)
			slice_id = slice_config.getSliceID()
		if command == "unregister":
			slice_id = pieces[1]
		return command, slice_id, slice_config

	def handle(self):
		data = self.request.recv(1024).strip()
		log.debug("Received " + data)
		command, slice_id, slice_config = self.parseCommand(data)
		response = ""
		try:
			if command == 'dump':
				scmap.dump_switch_controller_map()
				response = slice_registry_dump(False)
			else:
				if command == "register":
					slice_id = slice_config.getSliceID()
					controller_url = slice_config.getControllerURL()
					if controller_url == None:
						controller_url = VMOCGlobals.getDefaultControllerURL()
						slice_config.setControllerURL(controller_url)
					if slice_registry_is_registered(slice_config):
						slice_registry_unregister_slice(slice_id)
						scmap.remove_controller_connection(controller_url)
					slice_registry_register_slice(slice_config)
					scmap.add_controller_connection(controller_url, True)
					response = "Registered slice  : " + str(slice_config)
				elif command == "unregister":
					slice_id = slice_config.getSliceID()
					controller_url = slice_config.getControllerURL()
					slice_config = slice_registry_lookup_slice_config(slice_id)
					controller_url = slice_config.getControllerURL()
					slice_registry_unregister_slice(slice_id)
					scmap.remove_controller_connection(controller_url)
					response = "Unregistered slice : " + str(slice_id)
				else:
					response = "Illegal command "  + command
		except AssertionError, error:
			response = str(error)
		self.request.sendall(response)

class VMOCManagementInterface(threading.Thread):
 	def __init__(self, port, default_controller_url):
 		threading.Thread.__init__(self)
 		self._host, self._port = '', port
		self._default_controller_url = default_controller_url
		VMOCGlobals.setDefaultControllerURL(default_controller_url)

 	def run(self):
 		server = \
		    SocketServer.TCPServer((self._host, self._port), \
						   VMOCManagementServerHandler)
 		try:
 			server.serve_forever()
 		except BaseException:
 			server.shutdown()
 		log.info("VMOCMI.exit")

