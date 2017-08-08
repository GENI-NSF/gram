#----------------------------------------------------------------------
# Copyright (c) 2014-2016 Raytheon BBN Technologies
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

# Class to serve as resource manager for binding resources 
# for GRAM AM Authorization

from gcf.geni.auth.abac_resource_manager import Base_Resource_Manager
from gcf.geni.auth.base_authorizer import AM_Methods
import gcf.sfa.trust.credential as credential
import gcf.sfa.trust.gid as gid
from gcf.geni.util.tz_util import tzd
from .gram_manager import *
from .resources import *
from .stitching import *
import datetime
import dateutil.parser
import xml.dom.minidom

class GRAM_Resource_Manager(Base_Resource_Manager):
    def __init__(self):
        Base_Resource_Manager.__init__(self)

    def get_requested_allocation_state(self, aggregate_manager, method_name,
                                       arguments, options, credentials):
        resource_info = []
        amd = aggregate_manager._delegate

        if method_name in [AM_Methods.CREATE_SLIVER_V2, AM_Methods.ALLOCATE_V3]:

            creds = [credential.Credential(string=c) for c in credentials]
            
            # Grab info about  current slivers
            slices = SliceURNtoSliceObject._slices
            for slice_urn in slices:
                slice_obj = slices[slice_urn]
                slivers = slice_obj.getSlivers()
                for sliver_urn, sliver_obj in slivers.items():
                    user_urn = sliver_obj.getUserURN() 
                    start_time = str(datetime.datetime.utcnow())
                    end_time = str(sliver_obj.getExpiration())
                    if isinstance(sliver_obj, VirtualMachine):
                        sliver_info = {'sliver_urn' : sliver_urn,
                                       'slice_urn' : slice_urn, 
                                       'user_urn' : user_urn,
                                       'start_time' : start_time,
                                       'end_time' : end_time,
                                       'measurements' : {"NODE" : 1}
                                       }
                        resource_info.append(sliver_info)
                    elif isinstance(sliver_obj, NetworkLink):
                        self.processCapacity(resource_info, 
                                             slice_obj.getRequestRspec(),
                                             sliver_urn, slice_urn, user_urn, 
                                             start_time, end_time)


            # Grab all nodes from request rspec
            if 'rspec' in arguments and 'slice_urn' in arguments:
                rspec_raw = arguments['rspec']
                slice_urn = arguments['slice_urn']
                user_urn = gid.GID(string=options['geni_true_caller_cert']).get_urn()

                start_time = datetime.datetime.utcnow()
                if 'geni_start_time' in options:
                    raw_start_time = options['geni_start_time']
                    start_time = amd._nativeUTC(dateutil.parse.parse(raw_start_time))

                if 'geni_end_time' in options:
                    raw_end_time = options['geni_end_time']
                    end_time = amd.min_expire(creds, requested=raw_end_time)
                else:
                    end_time = amd.min_expire(creds)

                rspec = xml.dom.minidom.parseString(rspec_raw)
                nodes = rspec.getElementsByTagName('node')
                for node in nodes:
                    entry = {'sliver_urn' : 'not_set_yet',
                             'slice_urn' : slice_urn,
                             'user_urn' : user_urn,
                             'start_time' : str(start_time),
                             'end_time' : str(end_time),
                             'measurements' : {"NODE" : 1}
                             }
                    resource_info.append(entry)

                self.processCapacity(resource_info, rspec, 'not_set_yet', slice_urn, user_urn, 
                                start_time, end_time)

        elif method_name in [AM_Methods.RENEW_SLIVER_V2, AM_Methods.RENEW_V3]:

            # Grab the current slivers (as if we were calling createsliver/allocate with no new rspec
            resource_info = self.get_requested_allocation_state(aggregate_manager, 
                                                                AM_Methods.ALLOCATE_V3,
                                                                {}, {}, [])

            creds = [credential.Credential(string=c) for c in credentials]
            expiration = amd.min_expire(creds, max_duration=amd.max_lease)
            requested_str = arguments['expiration_time']
            requested = dateutil.parser.parse(requested_str, tzinfos=tzd)
            requested = amd._naiveUTC(requested)
            if 'geni_extend_alap' in options:
                requested = min(expiration, requested)
            requested = str(requested)

            if method_name == AM_Methods.RENEW_SLIVER_V2:
                the_slice_urn = arguments['slice_urn']
                the_slice = SliceURNtoSliceObject._slices[the_slice_urn]
                slivers = the_slice.getSlivers().values()
            else:
                urns = arguments['urns']
                the_slice, slivers = amd.decode_urns(urns)
            sliver_urns = [the_sliver.getSliverURN() for the_sliver in slivers]
            for entry in resource_info:
                if entry['sliver_urn'] in sliver_urns:
                    entry['end_time'] = requested

        else:
            pass

        return resource_info

    def processCapacity(self, resource_info, rspec, sliver_urn, slice_urn, 
                        user_urn, start_time, end_time):
        stitching = Stitching()
        error_string, error_code, details = stitching.parseRequestRSpec(rspec)
#        print "S = %s C = %s D = %s" % (error_string, error_code, details)
        if error_code == 0 and details is not None:
            for link_id, hop in details['my_hops_by_path_id'].items():
                for capacity in hop.getElementsByTagName('capacity'):
                    capacity_value = int(capacity.childNodes[0].nodeValue)
                    entry = { 'sliver_urn' : sliver_urn,
                              'slice_urn' : slice_urn,
                              'user_urn' : user_urn,
                              'start_time' : str(start_time),
                              'end_time' : str(end_time),
                              'measurements' : {"CAPACITY" : capacity_value}
                              }
                    resource_info.append(entry)
                        
                

