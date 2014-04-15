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

# AM API V2 version of Gram aggregate manager
# For testing against tools (Flack, portal) that speak AM API V2
# Since Gram is written to support V3
from gram import config
from geni.am.am2 import ReferenceAggregateManager
from geni.am.am2 import AggregateManager, AggregateManagerServer
from am3 import GramReferenceAggregateManager as GramReferenceAggregateManager_V3
from GramSecureXMLRPCServer import GramSecureXMLRPCServer
from GramSecureXMLRPCServer import GSecureXMLRPCRequestHandler
import base64
import os
import socket
import uuid
import zlib
import re

class GramReferenceAggregateManager(ReferenceAggregateManager):

    def __init__(self, root_cert, urn_authority, url, certfile, server,GRAM):

        ReferenceAggregateManager.__init__(self, root_cert, urn_authority, 
                                           url)
        self._v3_am = GRAM #GramReferenceAggregateManager_V3(root_cert, 
                           #                            urn_authority, 
                           #                            certfile, url)
        self._certfile = certfile
        self._am_type = "GRAM"
        self._server = server
        self._v3_am._server = server

    def GetVersion(self, options):
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

    def ListResources(self, credentials, options):
#        print  "OPTIONS = " + str(options)
        credentials = [self.transform_credential(c) for c in credentials]
        if 'geni_slice_urn' in options:
            slice_urn = options['geni_slice_urn']
            slice_urns = [slice_urn]


            ret_v3 = self._v3_am.Describe(slice_urns, credentials, options)
#            print "LR.Describe = " + str(ret_v3)
            if ret_v3['code']['geni_code'] != 0: return ret_v3
            result = ret_v3['value']['geni_rspec']

        else:
            ret_v3 = self._v3_am.ListResources(credentials, options)
            if ret_v3['code']['geni_code'] != 0: return ret_v3
            print "LR.ListResources = " + str(ret_v3)
            result = ret_v3['value']

#             result = self.advert_header()
#             component_manager_id = self._v3_am._my_urn
#             component_name = str(uuid.uuid4())
#             component_id = 'urn:publicid:geni:gpo:vm+' + component_name
#             exclusive = False
#             sliver_type = 'virtual-machine'
#             available = True
#             tmpl = '''  <node component_manager_id="%s"
#         component_name="%s"
#         component_id="%s"
#         exclusive="%s">
#     <sliver_type name="%s"/>
#     <available now="%s"/>
#   </node></rspec>
#   '''
#             result = self.advert_header() + \
#             (tmpl % (component_manager_id, component_name, \
#                          component_id, exclusive, sliver_type, available)) 

# #            result = self._v3_am.ListResources(credentials, options)
# #            if result['code'] != 0: return result
# #            result = result['value']

#         # Optionally compress the result
#         if 'geni_compressed' in options and options['geni_compressed']:
#             try:
#                 result = base64.b64encode(zlib.compress(result))
#             except Exception, exc:
#                 import traceback
#                 self.logger.error("Error compressing and encoding resource list: %s", traceback.format_exc())
#                 raise Exception("Server error compressing resource list", exc)


#        print "RET_V3 = " + str(type(ret_v3)) + " " + str(ret_v3)
        return self.successResult(result)

    def CreateSliver(self, slice_urn, credentials, rspec, users, options):
#        print "CREDS = " + str(credentials)
#        print "RSPEC = " + str(rspec)
#        print "USERS = " + str(users)
#        print "OPTS = " + str(options)
        credentials = [self.transform_credential(c) for c in credentials]
        urns = [slice_urn]
        # Pass to the allocate code that this is a V2 allocation
        options['AM_API_V2'] = True 

        # Allocate
        ret_allocate_v3 = self._v3_am.Allocate(slice_urn, credentials, \
                                          rspec, options)
#        print "ALLOC_RET " + str(ret_allocate_v3)

        if ret_allocate_v3['code']['geni_code'] != 0:
            return ret_allocate_v3

        # Provision
        options['geni_users'] = users # In v3, users is an option
        ret_provision_v3 = self._v3_am.Provision(urns, credentials, options)
#        print "PROV_RET " + str(ret_provision_v3)

        if ret_provision_v3['code']['geni_code'] != 0:
            return ret_provision_v3

        manifest = ret_provision_v3['value']['geni_rspec']

         # PerformOperationalAction(geni_start)
        #action = 'geni_start'
        #self._v3_am.PerformOperationalAction(urns, credentials, \
        #                                         action, options)
        return self.successResult(manifest)

    def DeleteSliver(self, slice_urn, credentials, options):
        credentials = [self.transform_credential(c) for c in credentials]
        urns = [slice_urn]
        ret_v3 = self._v3_am.Delete(urns, credentials, options)
        return ret_v3

    def SliverStatus(self, slice_urn, credentials, options):
        credentials = [self.transform_credential(c) for c in credentials]
        urns = [slice_urn]
        ret_v3 = self._v3_am.Status(urns, credentials, options)
#        print "RET_V3" + str(ret_v3)
        if ret_v3['code']['geni_code'] != 0: return ret_v3
        ret_v2 = ret_v3
        value = ret_v2['value']
        value['geni_resources'] = value['geni_slivers']
        slice_state = 'ready'
        for res_status in value['geni_resources']:
            res_status['geni_urn'] = res_status['geni_sliver_urn']
            state = 'ready'
            if res_status['geni_operational_status'] != 'geni_ready':
                state = 'pending'
                slice_state = state
            res_status['geni_status'] = state
        value['geni_status'] = slice_state
        ret_v2['value'] = value
#        print "SS RET = " + str(ret_v2)
        return ret_v2

    def RenewSliver(self, slice_urn, credentials, expiration_time, options):
        credentials = [self.transform_credential(c) for c in credentials]
        
        urns = [slice_urn]
        ret_v3 = self._v3_am.Renew(urns, credentials, 
                                      expiration_time, options)
        return ret_v3

    def Shutdown(self, slice_urn, credentials, options):
        credentials = [self.transform_credential(c) for c in credentials]
        ret_v3 = self._v3_am.Shutdown(slice_urn, credentials, options)
        return ret_v3

    def transform_credential(self, c):
        # Make these acceptable for V3 AM
        # Create a dictionary [geni_type='geni_sfa', geni_version=3, geni_value=c
        if isinstance(c, dict) and c.has_key('geni_value'):
            c = c['geni_value']
        if isinstance(c, str):
            return dict(geni_type='geni_sfa', geni_version=3, geni_value=c)
        else:
            msg = "Bad Arguments: Received illegal credential %s" % str(c)
            raise Exception(msg)

    def successResult(self, value):
        code_dict = dict(geni_code = 0, am_type = self._am_type, am_code=0)
        return dict(code=code_dict, value=value, output="")

class GramAggregateManagerServer(object):
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
        # FIXME: set logRequests=true if --debug
        self._server = GramSecureXMLRPCServer(addr, keyfile=keyfile,
                                          certfile=certfile, ca_certs=ca_certs)
        delegate = GramReferenceAggregateManager(trust_roots_dir, base_name,
                                             server_url, certfile, 
                                             self._server,
                                             GRAM)
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
