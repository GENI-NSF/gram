#----------------------------------------------------------------------
# Copyright (c) 2012 Raytheon BBN Technologies
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
"""
The GRAM Aggregate Manager.
Satisfies the V3 AM API and delegates functions to the GramManager
"""

from am3 import ReferenceAggregateManager, Slice
from am3 import AggregateManager, AggregateManagerServer

import logging

import geni
import mutex
import time
import geni.util.urn_util as urn
from geni.am.gram import gram_context
from gram.gram_manager import GramManager

class GramReferenceAggregateManager(ReferenceAggregateManager):
    '''A reference Aggregate Manager for GRAM '''

    # root_cert is a single cert or dir of multiple certs
    # that are trusted to sign credentials
    def __init__(self, root_cert, urn_authority, cert_file, url):
        ReferenceAggregateManager.__init__(self, root_cert, \
                                               urn_authority, cert_file, url)
        gram_context.GRAM_AM_URN = self._component_manager_id
#        print "CMID = " + self._component_manager_id
        # Startup the GRAM Manager
        self._gram_manager = GramManager()
        # mutex for managing simultaneous AM client threads
        self._mutex = mutex.mutex() 

        
    # Grab the mutex, or loop and wait until it is available
    def wait_for_lock(self):
        while not self._mutex.testandset():
            time.sleep(1)

    # Release the mutex
    def release_lock(self):
        self._mutex.unlock()

    def GetVersion(self, options):
        wait_for_lock()
        am3_return = ReferenceAggregateManager.GetVersion(self, options)
        release_lock()
        return am3_return

    # The list of credentials are options - some single cred
    # must give the caller required permissions.
    # The semantics of the API are unclear on this point, so
    # this is just the current implementation
    def ListResources(self, credentials, options):
        raise ApiErrorExeption(AM_API.UNSUPPORTED, \
                                   'ListResources not implemented')

    # The list of credentials are options - some single cred
    # must give the caller required permissions.
    # The semantics of the API are unclear on this point, so
    # this is just the current implementation
    def Allocate(self, slice_urn, credentials, rspec, options):
        """Allocate slivers to the given slice according to the given RSpec.
        Return an RSpec of the actually allocated resources.
        """
        self.logger.info('Allocate(%r)' % (slice_urn))
        self.expire_slivers()
        # Note this list of privileges is really the name of an operation
        # from the privilege_table in sfa/trust/rights.py
        # Credentials will specify a list of privileges, each of which
        # confers the right to perform a list of operations.
        # EG the 'info' privilege in a credential allows the operations
        # listslices, listnodes, policy
        privileges = (ALLOCATE_PRIV,)
        # Note that verify throws an exception on failure.
        # Use the client PEM format cert as retrieved
        # from the https connection by the SecureXMLRPCServer
        # to identify the caller.
        credentials = [self.normalize_credential(c) for c in credentials]
        credentials = [c['geni_value'] for c in filter(isGeniCred, credentials)]
        creds = self._cred_verifier.verify_from_strings(self._server.pem_cert,
                                                        credentials,
                                                        slice_urn,
                                                        privileges)

        wait_for_lock()
        am3_return = ReferenceAggregateManager.Allocate(self, slice_urn, 
                                                        credentials, rspec, 
                                                        options)
        if am3_return['code'] != 0:
            release_lock()
            return am3_return

        # If we get here, the credentials give the caller
        # all needed privileges to act on the given target.

        gram_return = self._gram_manager.allocate(slice_urn, credentials,
                                                  rspec, options)
        release_lock()

        return gram_return


    def Provision(self, urns, credentials, options):
        """Allocate slivers to the given slice according to the given RSpec.
        Return an RSpec of the actually allocated resources.
        """
        self.logger.info('Provision(%r)' % (urns))
        self.expire_slivers()

        the_slice, slivers = self.decode_urns(urns)

        # Note that verify throws an exception on failure.
        # Use the client PEM format cert as retrieved
        # from the https connection by the SecureXMLRPCServer
        # to identify the caller.
        credentials = [self.normalize_credential(c) for c in credentials]
        credentials = [c['geni_value'] for c in filter(isGeniCred, credentials)]
        wait_for_lock()
        am3_return = ReferenceAggregateManager.Provision(self, urns, 
                                                         credentials,
                                                         options)
        if am3_return['code'] != 0:
            release_lock()
            return am3_return

        gram_return = self._gram_manager.provision(the_slice.urn, credentials,
                                                   options)
        release_lock()
        return gram_return

    def Delete(self, urns, credentials, options):
        """Stop and completely delete the named slivers and/or slice.
        """
        self.logger.info('Delete(%r)' % (urns))
        self.expire_slivers()

        wait_for_lock()
        am3_return = ReferenceAggregateManager.Delete(self, urns, 
                                                         credentials,
                                                         options)
        if am3_return['code'] != 0:
            release_lock()
            return am3_return

        gram_return = self._gram_manager.delete(urns, options)
        release_lock()
        return gram_return


    def PerformOperationalAction(self, urns, credentials, action, options):
        """Peform the specified action on the set of objects specified by
        urns.
        """
        self.logger.info('PerformOperationalAction(%r)' % (urns))
        self.expire_slivers()

        wait_for_lock()
        am3_return = \
            ReferenceAggregateManager.PerformOperationalAction(self, \
                                                                   urns, \
                                                                   credentals,\
                                                                   action, \
                                                                   options)
        release_lock()
        return am3_return

#        raise ApiErrorExeption(AM_API.UNSUPPORTED, \
#                                   'PerformOperationalAction not implemented')

#        return self.successResult([s.status(errors[s.urn()])
#                                   for s in slivers])


    def Status(self, urns, credentials, options):
        '''Report as much as is known about the status of the resources
        in the sliver. The AM may not know.
        Return a dict of sliver urn, status, and a list of dicts resource
        statuses.'''
        # Loop over the resources in a sliver gathering status.
        wait_for_lock()
        am3_return = ReferenceAggregateManager.Status(self, urns, \
                                                          credentials, options)
        release_lock()
        return am3_return

    def Describe(self, urns, credentials, options):
        """Generate a manifest RSpec for the given resources.
        """
        self.logger.info('Describe(%r)' % (urns))
        self.expire_slivers()
        the_slice, slivers = self.decode_urns(urns)

        wait_for_lock()
        gram_return = self._gram_manager.describe(the_slice.urn, options)
        release_lock()
        return gram_return


    def Renew(self, urns, credentials, expiration_time, options):
        '''Renew the local sliver that is part of the named Slice
        until the given expiration time (in UTC with a TZ per RFC3339).
        Requires at least one credential that is valid until then.
        Return False on any error, True on success.'''

        wait_for_lock()
        gram_return = ReferenceAggregateManager.Renew(self, urns, credentals, \
                                                          expiration_time, \
                                                          options)
        release_lock()
        return gram_return


    def Shutdown(self, slice_urn, credentials, options):
        '''For Management Authority / operator use: shut down a badly
        behaving sliver, without deleting it to allow for forensics.'''
        wait_for_lock()
        am3_return = ReferenceAggregateManager.Shutdown(self, slice_urn, 
                                                        credentials, options)
        release_lock()
        return am3_return


class GramAggregateManagerServer(AggregateManagerServer):
        def __init__(self, addr, keyfile=None, certfile=None,
                 trust_roots_dir=None,
                 ca_certs=None, base_name=None):
            
            AggregateManagerServer.__init__(self, addr, \
                                                keyfile = keyfile, \
                                                certfile = certfile, \
                                                trust_roots_dir = trust_roots_dir, \
                                                ca_certs = ca_certs, \
                                                base_name = base_name)
            server_url = "https://%s:%d/" % addr
            delegate=GramReferenceAggregateManager(trust_roots_dir, \
                                                       base_name, \
                                                       certfile,  \
                                                       server_url)
            self._server.register_instance(AggregateManager(delegate))

