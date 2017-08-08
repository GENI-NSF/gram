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

# class to allow invoking calls on remote compute nodes
# This file contains a client interface 
#   (to be called by GRAM on the control node)
# And a server interface
#   (to be invoked in 'sudo' mode on each compute node


import SocketServer
import json
import socket
import subprocess
import tempfile

import config

MAX_SIZE = 8192

# Server interface
class ComputeNodeInterfaceHandler(SocketServer.BaseRequestHandler):

    # dictionary of permitted commands (ID => command)
    COMMAND_OVS_VSCTL =  1
    COMMAND_OVS_OFCTL =  2
    _PERMITTED_COMMANDS = {COMMAND_OVS_VSCTL:  ['ovs-vsctl', 'show'],
                           COMMAND_OVS_OFCTL:  ['ovs-ofctl', 'show', 'br-int']}

    # Use the template arguments as they are
    # But if an argument is provided for the argument of that index
    # Use template substitution
    def apply_arguments_to_template(self, command_template, args):
        command = []
        for i in range(len(command_template)):
            value = command_template[i]
            if args.has_key(i):
                value = command_template[i] % args[i]
            command.append(value)
        return command

    def handle(self):
        command_and_args_json = self.request.recv(MAX_SIZE).strip()
#        print "Got " + command_and_args_json
        command_and_args = json.loads(command_and_args_json)
#        print "CAA = " + str(command_and_args)
        command = command_and_args['command']
        args = command_and_args['args']
        if ComputeNodeInterfaceHandler._PERMITTED_COMMANDS.has_key(command):
            command_template = ComputeNodeInterfaceHandler._PERMITTED_COMMANDS[command]
            command_array = self.apply_arguments_to_template(command_template, args)
#           print "CL = " + str(command_array)
            response = subprocess.check_output(command_array)
#           print "Sending " + response
            self.request.sendall(response)

# Client interface the way it should be once the port is open
# Open a client connection, send command and receive response
# The command is a number, only among the set defined in ComputeNodeInterfaceHandler above
# The arguments are a dictionary that maps command value indices (0 for the first, 1 for the second)
# To values that should be template substituted
def compute_node_command(compute_host, command, args = {}):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    results = None
    if not ComputeNodeInterfaceHandler._PERMITTED_COMMANDS.has_key(command):
        config.logger.error("Illegal command for compute node interface : " + str(command))
        return results

    command_and_args = {'command':command, 'args':args}
    try:
        sock.connect((compute_host, config.compute_node_interface_port))
        sock.send(json.dumps(command_and_args))
        results = sock.recv(MAX_SIZE)
    finally:
        sock.close()
    return results

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 1:
        # Server case
        host_port = (socket.gethostname(), config.compute_node_interface_port)
        print "Starting command_node_interface server on port " + \
            str(config.compute_node_interface_port)
        server = SocketServer.TCPServer(host_port, ComputeNodeInterfaceHandler)
        server.serve_forever()
    else:
        # Client case : compute_node_interface host command
        compute_host = sys.argv[1]
        command = int(sys.argv[2])
        result = compute_node_command(compute_host, command)
        print "RESULT = " + str(result)
