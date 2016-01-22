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

"""A simple XML RPC server supporting SSL.

Based on this article:
   http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/81549

"""

#from SimpleXMLRPCServer import SimpleXMLRPCServer
#from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from gcf.geni.SecureThreadedXMLRPCServer import SecureThreadedXMLRPCRequestHandler
from gcf.geni.SecureThreadedXMLRPCServer import SecureThreadedXMLRPCServer
import SocketServer

# from geni.SecureXMLRPCServer import SecureXMLRPCRequestHandler
import ssl
import base64
import textwrap
import os
import threading

import gram.config

class GSecureXMLRPCRequestHandler(SecureThreadedXMLRPCRequestHandler):
    """A request handler that grabs the socket peer's certificate and
    makes it available while the request is handled.

    This is a thread-safe implementation of the SecureXMLRPCRequestHandler
    class that is distributed with gcf.  The thing that makes this
    thread-safe is the peer certificate is stashed in a thread-specific
    data structure rather than on the xml rpc server (which is what the
    gcf version does).
    """

    def setup(self):
        SecureThreadedXMLRPCRequestHandler.setup(self)
        gram.config.logger.info('setup by thread %s' % GSecureXMLRPCRequestHandler.request_specific_info.thread_name )
        
        self.log_request()

    def finish(self):
        # XXX do we want to delete the peercert attribute?
        # If so, use:        del self.server.peercert
        # self.server.peercert = None
        SecureThreadedXMLRPCRequestHandler.finish(self)
        
        

class GramSecureXMLRPCServer(SecureThreadedXMLRPCServer):
    """
        The SocketServer.ThreadingMixIn creates a new thread for each
        RPC.
    """
    def __init__(self, addr, requestHandler=GSecureXMLRPCRequestHandler,
                 logRequests=False, allow_none=False, encoding=None,
                 bind_and_activate=True, keyfile=None, certfile=None,
                 ca_certs=None):
        SecureThreadedXMLRPCServer.__init__(self, addr, requestHandler, 
                                            logRequests,
                                            allow_none, encoding, 
                                            bind_and_activate, 
                                            keyfile, certfile, ca_certs)

        

