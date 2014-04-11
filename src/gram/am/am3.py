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
"""
The GPO Reference Aggregate Manager v3, showing how to implement
the GENI AM API version 3. This AggregateManager has only fake resources.
Invoked from gcf-am.py
The GENI AM API is defined in the AggregateManager class.
"""

import base64
import collections
import datetime
import dateutil.parser
import logging
import os
import socket
import time
import traceback
import uuid
import xml.dom.minidom as minidom
import zlib
import re

import geni
from geni.util.urn_util import publicid_to_urn
import geni.util.urn_util as urn
from GramSecureXMLRPCServer import GramSecureXMLRPCServer
from GramSecureXMLRPCServer import GSecureXMLRPCRequestHandler
from geni.am.am3 import *

from gram import config
from gram import constants
from gram.gram_manager import GramManager
from gram.rspec_handler import generateAdvertisement
import gram.open_stack_interface

class GramReferenceAggregateManager(ReferenceAggregateManager):
    '''A reference Aggregate Manager that manages fake resources.'''

    # root_cert is a single cert or dir of multiple certs
    # that are trusted to sign credentials
    def __init__(self, root_cert, urn_authority, certfile, url):

        self._certfile = certfile
        self._component_manager_id = self.readURNFromCertfile(certfile)
        config.gram_am_urn = self._component_manager_id

        ReferenceAggregateManager.__init__(self, root_cert, \
                                               urn_authority, url)
        # Startup the GRAM Manager
        self._gram_manager = GramManager(certfile)

    def GetVersion(self, options):
        #self._gram_manager.expire_slivers()
        result = ReferenceAggregateManager.GetVersion(self, options)
        hostname = socket.getfqdn()

        version_file = open('/home/gram/gram/src/GRAMVERSION','r')
        line = version_file.readline()
        v = re.search("(\d*)\.(\d*)",line)
        version_file.close()
        if v:
          gram_version = v.group(1) + "." + v.group(2)


        v3_url = "https://%s:%d" % (hostname, config.gram_am_port)
        v2_url = "https://%s:%d" % (hostname, config.gram_am_v2_port)
        geni_api_versions = {'2' : v2_url, '3' : v3_url}
        result['value']['GRAM_version'] = gram_version
        result['value']['geni_api_versions'] = geni_api_versions
        result['code']['am_type'] = 'GRAM'
        return result


    # The list of credentials are options - some single cred
    # must give the caller required permissions.
    # The semantics of the API are unclear on this point, so
    # this is just the current implementation
    def ListResources(self, credentials, options):
        self.logger.info('ListResources')
        #self._gram_manager.expire_slivers()
        creds = self.validate_credentials(credentials, (), None)


        if 'geni_slice_urn' in options:
            slice_urn = options['geni_slice_urn']
            slice_urns = [slice_urn]
            ret = self.Describe(slice_urns, credentials, options)
            return ret

        stitching_state = self._gram_manager.getStitchingState()
        result = generateAdvertisement(self._gram_manager._aggregate_urn, \
                                           stitching_state)
        
        if 'geni_compressed' in options and options['geni_compressed']:
            try:
                result = base64.b64encode(zlib.compress(result))
            except Exception, exc:
                self.logger.error("Error compressing and encoding resource list")
                
        return self.successResult(result)

    # The list of credentials are options - some single cred
    # must give the caller required permissions.
    # The semantics of the API are unclear on this point, so
    # this is just the current implementation
    def Allocate(self, slice_urn, credentials, rspec, options):
        """Allocate slivers to the given slice according to the given RSpec.
        Return an RSpec of the actually allocated resources.
        """
        self.logger.info('Allocate(%r)' % (slice_urn))
        # self._gram_manager.expire_slivers()
        # Note this list of privileges is really the name of an operation
        # from the privilege_table in sfa/trust/rights.py
        # Credentials will specify a list of privileges, each of which
        # confers the right to perform a list of operations.
        # EG the 'info' privilege in a credential allows the operations
        # listslices, listnodes, policy
        privileges = (ALLOCATE_PRIV,)
        creds = self.validate_credentials(credentials, privileges, slice_urn)

        # If we get here, the credentials give the caller
        # all needed privileges to act on the given target.
        gram_return = self._gram_manager.allocate(slice_urn, creds, rspec,
                                                  options)

        return gram_return


    def Provision(self, urns, credentials, options):
        """Allocate slivers to the given slice according to the given RSpec.
        Return an RSpec of the actually allocated resources.
        """
        self.logger.info('Provision(%r)' % (urns))
        #self._gram_manager.expire_slivers()

        # Set the_slice to the slice_object that contains the slivers to
        # be provisioned.  Set slivers to the silver_objects that need to
        # be provisioned.  If the Provision API call was given just a 
        # slice_urn, slivers will include all sliver_objects in the slice
        the_slice, slivers = self._gram_manager.decode_urns(urns)

        if not the_slice: 
            return self._no_slice_found(urns)

        # Note this list of privileges is really the name of an operation
        # from the privilege_table in sfa/trust/rights.py
        # Credentials will specify a list of privileges, each of which
        # confers the right to perform a list of operations.
        # EG the 'info' privilege in a credential allows the operations
        # listslices, listnodes, policy
        privileges = (PROVISION_PRIV,)
        # Note that verify throws an exception on failure.
        # Use the client PEM format cert as retrieved
        # from the https connection by the SecureXMLRPCServer
        # to identify the caller.
        creds = self.validate_credentials(credentials, privileges, \
                                              the_slice.getSliceURN())

        return self._gram_manager.provision(the_slice, slivers, creds, options)


    def Delete(self, urns, credentials, options):
        """Stop and completely delete the named slivers and/or slice.
        """
        self.logger.info('Delete(%r)' % (urns))
        #self._gram_manager.expire_slivers()

        # Set the_slice to the slice_object that contains the slivers to
        # be provisioned.  Set slivers to the silver_objects that need to
        # be provisioned.  If the Provision API call was given just a 
        # slice_urn, slivers will include all sliver_objects in the slice
 
        the_slice, slivers = self._gram_manager.decode_urns(urns)
        if not the_slice:
            return self._no_slice_found(urns)

        privileges = (DELETESLIVERPRIV,)
        creds = self.validate_credentials(credentials, privileges, \
                                              the_slice.getSliceURN())

        return self._gram_manager.delete(the_slice, slivers, options)


    def PerformOperationalAction(self, urns, credentials, action, options):
        """Peform the specified action on the set of objects specified by
        urns.
        """
        self.logger.info('PerformOperationalAction(%r,%s)' % (urns,action))
        #self._gram_manager.expire_slivers()

        the_slice, slivers = self._gram_manager.decode_urns(urns)
        print slivers
        if not the_slice:
            return self._no_slice_found(urns)

        # Note this list of privileges is really the name of an operation
        # from the privilege_table in sfa/trust/rights.py
        # Credentials will specify a list of privileges, each of which
        # confers the right to perform a list of operations.
        # EG the 'info' privilege in a credential allows the operations
        # listslices, listnodes, policy
        privileges = (PERFORM_ACTION_PRIV,)
        creds = self.validate_credentials(credentials, privileges, \
                                              the_slice.getSliceURN())

        return self._gram_manager.performOperationalAction(the_slice, slivers,
                                                           action, options)


        # A place to store errors on a per-sliver basis.
        # {sliverURN --> "error", sliverURN --> "error", etc.}
        astates = []
        ostates = []
        if action == 'geni_start':
            astates = [STATE_GENI_PROVISIONED]
            ostates = [OPSTATE_GENI_NOT_READY]
        elif action == 'geni_restart':
            astates = [STATE_GENI_PROVISIONED]
            ostates = [OPSTATE_GENI_READY]
        elif action == 'geni_stop':
            astates = [STATE_GENI_PROVISIONED]
            ostates = [OPSTATE_GENI_READY]
        else:
            msg = "Unsupported: action %s is not supported" % (action)
            raise ApiErrorException(AM_API.UNSUPPORTED, msg)

        # Handle best effort. Look ahead to see if the operation
        # can be done. If the client did not specify best effort and
        # any resources are in the wrong state, stop and return an error.
        # But if the client specified best effort, trundle on and
        # do the best you can do.
        errors = collections.defaultdict(str)
        for sliver in slivers:
            # ensure that the slivers are provisioned
            if (sliver.getAllocationState() not in astates
                or sliver.getOperationalState() not in ostates):
                msg = "%d: Sliver %s is not in the right state for action %s."
                msg = msg % (AM_API.UNSUPPORTED, sliver.getSliverURN(), action)
                errors[sliver.getSliverURN()] = msg
        best_effort = False
        if 'geni_best_effort' in options:
            best_effort = bool(options['geni_best_effort'])
        if not best_effort and errors:
            raise ApiErrorException(AM_API.UNSUPPORTED,
                                    "\n".join(errors.values()))

        # Perform the state changes:
        for sliver in slivers:
            if (action == 'geni_start'):
                if (sliver.getAllocationState() in astates
                    and sliver.getOperationalState() in ostates):
                    sliver.setOperationalState(OPSTATE_GENI_READY)
            elif (action == 'geni_restart'):
                if (sliver.getAllocationState() in astates
                    and sliver.getOperationalState() in ostates):
                    sliver.setOperationalState(OPSTATE_GENI_READY)
            elif (action == 'geni_stop'):
                if (sliver.getAllocationState() in astates
                    and sliver.getOperationalState() in ostates):
                    sliver.setOperationalState(OPSTATE_GENI_NOT_READY)
            else:
                # This should have been caught above
                msg = "Unsupported: action %s is not supported" % (action)
                raise ApiErrorException(AM_API.UNSUPPORTED, msg)

        # If we're starting VM's, 
        # Wait for all VM's to be 'ready' (operational state)
        # if action == 'geni_start':
        #     while True:
        #         every_vm_ready = True
        #         gram.open_stack_interface.updateOperationalStatus(the_slice);
        #         for vm in the_slice.getVMs():
        #             if vm.getOperationalState() != constants.ready: 
        #                 every_vm_ready = False
        #                 print "VM " + str(vm) + " is not ready"
        #                 break
        #         if every_vm_ready: 
        #             print "ALL VM's READY"
        #             break
        #         time.sleep(1)

        # Save the state with the new allocation and operational states
        self._gram_manager.persist_state()

        return self.successResult([s.status(errors[s.getSliverURN()])
                                   for s in slivers])


    def Status(self, urns, credentials, options):
        '''Report as much as is known about the status of the resources
        in the sliver. The AM may not know.
        Return a dict of sliver urn, status, and a list of dicts resource
        statuses.'''
        # Loop over the resources in a sliver gathering status.
        #import pdb; pdb.set_trace()
        self.logger.info('got here')
        self.logger.info('Status(%r)' % (urns))
        #self._gram_manager.expire_slivers()
        the_slice, slivers = self._gram_manager.decode_urns(urns)

        if not the_slice:
            return self._no_slice_found(urns)

        privileges = (SLIVERSTATUSPRIV,)
        creds = self.validate_credentials(credentials, privileges, \
                                              the_slice.getSliceURN())
        return self._gram_manager.status(the_slice, slivers, options)


    def Describe(self, urns, credentials, options):
        """Generate a manifest RSpec for the given resources.
        """
        self.logger.info('Describe(%r)' % (urns))
        #self._gram_manager.expire_slivers()

        the_slice, slivers = self._gram_manager.decode_urns(urns)
        if not the_slice:
            return self._no_slice_found(urns)

        privileges = (SLIVERSTATUSPRIV,)
        creds = self.validate_credentials(credentials, privileges, \
                                              the_slice.getSliceURN())

        return self._gram_manager.describe(the_slice, slivers, options)


    def Renew(self, urns, credentials, expiration_time, options):
        '''Renew the local sliver that is part of the named Slice
        until the given expiration time (in UTC with a TZ per RFC3339).
        Requires at least one credential that is valid until then.
        Return False on any error, True on success.'''
       
        self.logger.info('Renew(%r, %r)' % (urns, expiration_time))
        #self._gram_manager.expire_slivers()

        the_slice, slivers = self._gram_manager.decode_urns(urns)
        if not the_slice:
            return self._no_slice_found(urns)

        privileges = (RENEWSLIVERPRIV,)
        creds = self.validate_credentials(credentials, privileges, \
                                              the_slice.getSliceURN())

        gram_ret = self._gram_manager.renew_slivers(the_slice,slivers, creds, expiration_time)
        
        return gram_ret

    def Shutdown(self, slice_urn, credentials, options):
        '''For Management Authority / operator use: shut down a badly
        behaving sliver, without deleting it to allow for forensics.'''
        self.logger.info('Shutdown(%r)' % (slice_urn))
        #self._gram_manager.expire_slivers()
        privileges = (SHUTDOWNSLIVERPRIV,)
        creds = self.validate_credentials(credentials, privileges, \
                                              slice_urn)
        gram_ret = self._gram_manager.shutdown_slice(slice_urn)

        return gram_ret

    # Read URN from certificate file
    def readURNFromCertfile(self, certfile):
            import sfa.trust.certificate
            cert =  sfa.trust.certificate.Certificate()
            cert.load_from_file(certfile)
            san = cert.get_data('subjectAltName')
            sans = san.split(', ');
            urns = [s[4:] for s in filter(lambda x: 'publicid' in x, sans)]
            urn = urns[0]
            return urn

    # Return error if no slice found for set of URN's
    def _no_slice_found(self, urns):
        if len(urns) > 0:
            return self.errorResult(constants.UNKNOWN_SLICE, 'URN not found: ' + urns[0])
        else:
            return self.errorResult(constants.UNKNOWN_SLICE, 'No URNs provided to AM call')

    def errorResult(self,code,message):
        ret =  {'code' : {'geni_code' : code}, 'value' : '', 'output' : message}
        self.logger.info("No slice found, returning: " + str(ret))
        return ret

    # Does the given set of credentials allow all the following privileges?
    def validate_credentials(self, credentials, privileges, slice_urn):
        credentials = [self.normalize_credential(c) for c in credentials]
        credentials = \
            [c['geni_value'] for c in filter(isGeniCred, credentials)]
        creds = self._cred_verifier.verify_from_strings(
            GSecureXMLRPCRequestHandler.get_pem_cert(),
            credentials,
            slice_urn,
            privileges)
        return creds

    # See https://www.protogeni.net/trac/protogeni/wiki/RspecAdOpState
    def advert_header(self):
        header = '''<?xml version="1.0" encoding="UTF-8"?>
<rspec xmlns="http://www.geni.net/resources/rspec/3"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xsi:schemaLocation="%s"
       type="advertisement">'''
        return header
        

class GramAggregateManagerServer(object):
    """An XMLRPC Aggregate Manager Server. Delegates calls to given delegate,
    or the default printing AM."""

    def __init__(self, addr, keyfile=None, certfile=None,
                 trust_roots_dir=None,
                 ca_certs=None, base_name=None,GRAM=None):
        # ca_certs arg here must be a file of concatenated certs
        if ca_certs is None:
            raise Exception('Missing CA Certs')
        elif not os.path.isfile(os.path.expanduser(ca_certs)):
            raise Exception('CA Certs must be an existing file of accepted root certs: %s' % ca_certs)

        # Decode the addr into a URL. Is there a pythonic way to do this?
        server_url = "https://%s:%d/" % addr
        delegate = GRAM #GramReferenceAggregateManager(trust_roots_dir, base_name,
                        #                     certfile, 
                        #                     server_url)
        # FIXME: set logRequests=true if --debug
        self._server = GramSecureXMLRPCServer(addr, keyfile=keyfile,
                                          certfile=certfile, ca_certs=ca_certs)
        self._server.register_instance(AggregateManager(delegate))
        # Set the server on the delegate so it can access the
        # client certificate.
        delegate._server = self._server

        if not base_name is None:
            global RESOURCE_NAMESPACE
            RESOURCE_NAMESPACE = base_name

    def serve_forever(self):
        self._server.serve_forever()

    def register_instance(self, instance):
        # Pass the AM instance to the generic XMLRPC server,
        # which lets it know what XMLRPC methods to expose
        self._server.register_instance(instance)
