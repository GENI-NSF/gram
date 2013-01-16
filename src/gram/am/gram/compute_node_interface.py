#!/usr/bin/python

# class to allow invoking calls on remote compute nodes
# This file contains a client interface 
#   (to be called by GRAM on the control node)
# And a server interface
#   (to be invoked in 'sudo' mode on each compute node


import SocketServer
import socket
import subprocess
import tempfile

import config

MAX_SIZE = 8192

# Server interface
class ComputeNodeInterfaceHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        command = self.request.recv(MAX_SIZE).strip()
#        print "Got " + command
        parsed_command = command.split(' ')
        response = subprocess.check_output(parsed_command)
#        print "Sending " + response
        self.request.sendall(response)

# Client interface the way it should be once the port is open
# Open a client connection, send command and receive response
def compute_node_command(compute_host, command):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    results = None
    try:
        sock.connect((compute_host, config.compute_node_interface_port))
        sock.send(command)
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
        command = sys.argv[2]
        result = compute_node_command(compute_host, command)
        print "RESULT = " + str(result)
