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
	# ping
	# Return command, controller_url, slice_config [last two could be None]
	def parseCommand(self, command_line):
		pieces=command_line.split(' ')
		command = pieces[0]
		slice_id = None
		slice_config = None
		if command == 'register' or command == 'unregister':
			slice_config_json = ' '.join(pieces[1:])
			slice_config_attribs = json.loads(slice_config_json)
			slice_config = VMOCSliceConfiguration(\
				attribs=slice_config_attribs)
			slice_id = slice_config.getSliceID()
		return command, slice_id, slice_config

	# Handle the request, wrapping in an exception black
	def handle(self):
		data = self.request.recv(1024).strip()
		if data != 'ping':
			log.debug("Received " + data)
		command, slice_id, slice_config = self.parseCommand(data)
		response = ""
		try:
			if command == 'dump':
				response1 = scmap.dump_switch_controller_map()
				response2 = slice_registry_dump(False)
				response = response1 + "\n" + response2
			elif command == 'ping':
				response = ''
			elif command == "register":
				response = self.handleRegister(slice_config)
			elif command == "unregister":
				response = self.handleUnregister(slice_config)
			else:
				response = "Illegal command " + command
		except AssertionError, error:
			response = str(error)
		self.request.sendall(response)

	# Handle the register request, returning response 
	def handleRegister(self, slice_config):
		slice_id = slice_config.getSliceID()
		vlan_configs = slice_config.getVLANConfigurations()


		# Insert default controller if none provided
		for vc in vlan_configs:
			if not vc.getControllerURL() or len(vc.getControllerURL()) == 0:
				vc.setControllerURL(VMOCGlobals.getDefaultControllerURL())

		if slice_registry_is_registered(slice_config):
			scmap.remove_controller_connections_for_slice(slice_id)
			slice_registry_unregister_slice(slice_id)
		slice_registry_register_slice(slice_config)
		for vc in vlan_configs:
			vlan = vc.getVLANTag()
			controller_url = vc.getControllerURL()
			scmap.create_controller_connection(controller_url, \
								   vlan, True)
		response = "Registered slice  : " + str(slice_config)
		return response

	def handleUnregister(self, slice_config):
		slice_id = slice_config.getSliceID()
		slice_config = \
		    slice_registry_lookup_slice_config_by_slice_id(slice_id)
		if slice_config:
			scmap.remove_controller_connections_for_slice(slice_id)
			slice_registry_unregister_slice(slice_id)
			response = "Unregistered slice : " + str(slice_id)
		else:
			response = "No such slice registered: " + slice_id
		return response


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

