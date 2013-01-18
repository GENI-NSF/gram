# AM API V2 version of Gram aggregate manager
# For testing against tools (Flack, portal) that speak AM API V2
# Since Gram is written to support V3
from geni.am.am2 import ReferenceAggregateManager
from geni.am.am2 import AggregateManager, AggregateManagerServer
from am3 import GramReferenceAggregateManager as GramReferenceAggregateManager_V3
import base64
import zlib
import uuid

class GramReferenceAggregateManager(ReferenceAggregateManager):

    def __init__(self, root_cert, urn_authority, url, certfile, server):

        ReferenceAggregateManager.__init__(self, root_cert, urn_authority, 
                                           url)
        self._v3_am = GramReferenceAggregateManager_V3(root_cert, 
                                                       urn_authority, 
                                                       certfile, url)
        self._certfile = certfile
        self._am_type = "gram"
        self._server = server
        self._v3_am._server = server

    def GetVersion(self, options):
        return ReferenceAggregateManager.GetVersion(self, options)

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
            result = self.advert_header()
            component_manager_id = self._v3_am._my_urn
            component_name = str(uuid.uuid4())
            component_id = 'urn:publicid:geni:gpo:vm+' + component_name
            exclusive = False
            sliver_type = 'virtual-machine'
            available = True
            tmpl = '''  <node component_manager_id="%s"
        component_name="%s"
        component_id="%s"
        exclusive="%s">
    <sliver_type name="%s"/>
    <available now="%s"/>
  </node></rspec>
  '''
            result = self.advert_header() + \
            (tmpl % (component_manager_id, component_name, \
                         component_id, exclusive, sliver_type, available)) 

#            result = self._v3_am.ListResources(credentials, options)
#            if result['code'] != 0: return result
#            result = result['value']

        # Optionally compress the result
        if 'geni_compressed' in options and options['geni_compressed']:
            try:
                result = base64.b64encode(zlib.compress(result))
            except Exception, exc:
                import traceback
                self.logger.error("Error compressing and encoding resource list: %s", traceback.format_exc())
                raise Exception("Server error compressing resource list", exc)


#        print "RET_V3 = " + str(type(ret_v3)) + " " + str(ret_v3)
        return self.successResult(result)

    def CreateSliver(self, slice_urn, credentials, rspec, users, options):
#        print "CREDS = " + str(credentials)
#        print "RSPEC = " + str(rspec)
#        print "USERS = " + str(users)
#        print "OPTS = " + str(options)
        credentials = [self.transform_credential(c) for c in credentials]
        urns = [slice_urn]
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
                                                       certfile, 
                                                       self._server)
            self._server.register_instance(AggregateManager(delegate))

