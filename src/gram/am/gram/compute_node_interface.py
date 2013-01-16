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
def compute_node_command_future(compute_host, command):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    results = None
    try:
        sock.connect((compute_host, config.compute_node_interface_port))
        results =sock.send(command)
    finally:
        sock.close()
    return results

# Client interface: Open a connection, send command and return result
# We need to open up a port. Until then, use SSH/SCP
def compute_node_command(compute_host, command):
    tmp = tempfile.NamedTemporaryFile(dir='/tmp')
    full_command = 'echo ' + '"' + command + '"' + " | nc localhost " + \
        str(config.compute_node_interface_port)
    tmp.write(full_command)
    tmp.flush()
    copy_file_command = ['scp', '-q', tmp.name, '%s:/tmp' % compute_host]
    subprocess.call(copy_file_command)
    execute_remote_process_command = \
        ["ssh", compute_host, "source", tmp.name]
    results = subprocess.check_output(execute_remote_process_command)
    tmp.close()
    remote_rm_command = ["ssh", compute_host, "rm", tmp.name]
    subprocess.call(remote_rm_command)
    return results

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 1:
        # Server case
        host_port = ('localhost', config.compute_node_interface_port)
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
