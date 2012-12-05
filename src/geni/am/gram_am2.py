# AM API V2 version of Gram aggregate manager
# For testing against tools (Flack, portal) that speak AM API V2
# Since Gram is written to support V3
from am2 import Slice, ReferenceAggregateManager
from am2 import AggregateManager, AggregateManagerServer
from am3 import ReferenceAggregateManager as ReferenceAggregateManager_V3, Slice as Slice_V3

class GramReferenceAggregateManager(ReferenceAggregateManager):

    def __init__(self, root_cert, urn_authority, url, server):
        ReferenceAggregateManager.__init__(self, root_cert, urn_authority, url)
        self._v3_am = ReferenceAggregateManager_V3(root_cert, urn_authority, url)
        self._server = server
        self._v3_am._server = server
        
    def GetVersion(self, options):
        return ReferenceAggregateManager.GetVersion(self, options)

    def ListResources(self, credentials, options):
        print  "OPTIONS = " + str(options)
        credentials = [self.transform_credential(c) for c in credentials]
        if 'geni_slice_urn' in options:
            slice_urn = options['geni_slice_urn']
            slice_urns = [slice_urn]
            ret_v3 = self._v3_am.Describe(slice_urns, credentials, options)
        else:
            ret_v3 = self._v3_am.ListResources(credentials, options)
        return ret_v3

    def CreateSliver(self, slice_urn, credentials, rspec, users, options):
        credentials = [self.transform_credential(c) for c in credentials]
        urns = [slice_urn]
        # Allocate
        ret_v3 = self._v3_am.Allocate(self, slice_urn, credentials, \
                                          rspec, options)
        # Provision
        ret_v3 = self._v3_am.Provision(self, urns, credentials, options)
        manifest = ret_v3['geni_rspec']
        # PerformOperationalAction(geni_start)
        action = 'geni_start'
        self._v3_am.PerformOperationalAction(urns, credentials, \
                                                 action, options)
        return self.successResult(manifest)

    def DeleteSliver(self, slice_urn, credentials, options):
        credentials = [self.transform_credential(c) for c in credentials]
        urns = [slice_urn]
        ret_v3 = self._v3_am.Delete(urns, credentials, options)
        return self.successResult(True)

    def SliverStatus(self, slice_urn, credentials, options):
        credentials = [self.transform_credential(c) for c in credentials]
        urns = [slice_urn]
        ret_v3 = self._v3_am.Status(urns, credentials, options)
        res_status = list()
        resources = self._v3_am.catalog(slice_urn)
        # This is a V3 slice, not a v2 slice
        slice = self._v3_am._slices[slice_urn]
        for res in resources:
            res_status.append(dict(geni_urn=self.resource_urn(res),
                                   geni_status = res.status,
                                   geni_error=''))
        slice_status = slice.status(resources)
        result = dict(geni_urn=slice_urn,
                      geni_status=slice_status,
                      geni_resources=res_status)
        return result

    def RenewSliver(self, slice_urn, credentials, expiration_time, options):
        credentials = [self.transform_credential(c) for c in credentials]
        urns = [slice_urn]
        ret_v3 = self._v3_am.Renew(urns, credentials, 
                                      expiration_time, options)
        return ret_v3

    def Shutdown(self, slice_urn, credentials, options):
        credentials = [self.transform_credential(c) for c in credentials]
        self._v3_am.Shutdown(slice_urn, credentials, options)
        return ReferenceAggregateManager.Shutdown(self, slice_urn, \
                                                      credentials, options)

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
                                                       base_name, server_url, \
                                                       self._server)
            self._server.register_instance(AggregateManager(delegate))




