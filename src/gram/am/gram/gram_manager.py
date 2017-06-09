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

import datetime
import dateutil
import os
import getpass
import signal
import time

import config
import constants
from gcf.sfa.trust.certificate import Certificate
from resources import GramImageInfo, Slice, VirtualMachine, NetworkLink
import rspec_handler
import open_stack_interface
import stitching
import utils
import vlan_pool
import Archiving
import threading
import thread

from vmoc.VMOCClientInterface import VMOCClientInterface
from vmoc.VMOCConfig import VMOCSliceConfiguration, VMOCVLANConfiguration

class SliceURNtoSliceObject :
    """
        Class maps slice URNs to slice objects
    """
    _slices = {}   # Slice objects at this aggregate, indexed by slice urn
    _lock = threading.RLock()

    @staticmethod
    def get_slice_object(slice_urn) :
        """
            Returns the Slice object that has the given slice_urn.
        """
        with SliceURNtoSliceObject._lock :
            if slice_urn in SliceURNtoSliceObject._slices :
                return SliceURNtoSliceObject._slices[slice_urn]
            else :
                return None
            
    @staticmethod
    def get_slice_objects() :
        """
            Returns a list of all Slice objects at this aggregate .
        """
        with SliceURNtoSliceObject._lock :
            return SliceURNtoSliceObject._slices.values()

    @staticmethod
    def set_slice_object(slice_urn, slice_object) :
        with SliceURNtoSliceObject._lock :
            SliceURNtoSliceObject._slices[slice_urn] = slice_object

    @staticmethod
    def remove_slice_object(slice_urn) :
        with SliceURNtoSliceObject._lock :
            del SliceURNtoSliceObject._slices[slice_urn]


class GramManager :
    """
        Only one instances of this class is created.
    """
    def __init__(self, certfile) :

        # Grab the certfile and extract the aggregate URN
        self._certfile = certfile
        self._cert = Certificate(filename=certfile)
        cert_data = self._cert.get_data()
        cert_data_parts = cert_data.split(',')
        for part in cert_data_parts:
            if part.find('URI:urn:publicid')>=0:
                self._aggregate_urn = part[4:]

        self._aggregate_urn = config.aggregate_id
        self._internal_vlans = \
            vlan_pool.VLANPool(config.internal_vlans, "INTERNAL")

        open_stack_interface.init() # OpenStack related initialization

        # Set up a signal handler to clean up on a control-c
        # signal.signal(signal.SIGINT, open_stack_interface.cleanup)

        self._snapshot_directory = None
        if config.gram_snapshot_directory:
            self._snapshot_directory = \
                config.gram_snapshot_directory + "/" + getpass.getuser()

        # Set max allocation and lease times
        self._max_alloc_time = \
            datetime.timedelta(minutes=config.allocation_expiration_minutes ) 
        self._max_lease_time = \
            datetime.timedelta(minutes=config.lease_expiration_minutes) 

        self._stitching = stitching.Stitching()

        self._persistent_state = {"FOO" : "BAR"}

        # Client interface to VMOC - update VMOC on current
        # State of all slices and their associated 
        # network VLAN's and controllers
        if config.vmoc_slice_autoregister:
            VMOCClientInterface.startup()
            config.logger.info("Started VMOC Client Interface from gram manager")

        # Recover state from snapshot, if configured to do so
        self.restore_state()

        # Reconcile restored state with state of OpenStack
        # Are any resources no longer there? If so delete slices
        self.reconcile_state()

        # If any slices restored from snapshot, report to VMOC
        with SliceURNtoSliceObject._lock:
            for slice_name in SliceURNtoSliceObject._slices:
                the_slice = SliceURNtoSliceObject._slices[slice_name]
                self.registerSliceToVMOC(the_slice)
        
        # Remove extraneous snapshots
        self.prune_snapshots()

        thread.start_new_thread(self.periodic_cleanup,())

    def getStitchingState(self) : return self._stitching

    # Maintain some persistent state on the gram manager that 
    # is stored into and retrieved from snapshots
    def setPersistentState(self, ps) : self._persistent_state = ps
    def getPersistentState(self) : return self._persistent_state;

    # Cleanup all allocated slivers and return error code
    # To be called from all error returns from allocate
    def cleanup_slivers(self, slivers, slice_object):
        for sliver_object in slivers:
            slice_object.removeSliver(sliver_object)

    def allocate(self, slice_urn, creds, rspec, options) :

        """
            AM API V3 method.

            Request reservation of GRAM resources.  We assume that by the 
            time we get here the caller's credentials have been verified 
            by the gcf framework (see am3.py).

            Returns None if successful.
            Returns an error string on failure.
        """
        config.logger.info('Allocate called for slice %r' % slice_urn)

        # Grab user urn out of slice credentail
        user_urn  = None
        if len(creds) == 1:
            user_urn = creds[0].gidCaller.urn

        # Check if we already have slivers for this slice
        slice_object = SliceURNtoSliceObject.get_slice_object(slice_urn)
        if slice_object == None :
            # This is a new slice at this aggregate.  Create Slice object 
            # and add it the list of slices at this AM
            slice_object = Slice(slice_urn)
            SliceURNtoSliceObject.set_slice_object(slice_urn, slice_object)

        # Lock this slice so nobody else can mess with it during allocation
        with slice_object.getLock() :
            # Parse the request rspec.  Get back any error message from parsing
            # the rspec and a list of slivers created while parsing
            # Also OF controller, if any
            err_output, err_code, slivers, controller_link_info = \
                rspec_handler.parseRequestRspec(self._aggregate_urn,
                                                slice_object, rspec, 
                                                self._stitching)

            if err_output != None :
                # Something went wrong.  First remove from the slice any sliver
                # objects created while parsing the bad rspec
                self.cleanup_slivers(slivers, slice_object)
                
                # Return an error struct.
                code = {'geni_code': err_code}
                return {'code': code, 'value': '', 'output': err_output}

            # If we're associating an OpenFlow controller to 
            # any link of this slice, 
            # Each VM must go on its own host. If there are more nodes
            # than hosts, we fail
            if len(controller_link_info) > 0:
                hosts = open_stack_interface._listHosts('compute')
                num_vms = 0
                for sliver in slivers:
                    if isinstance(sliver, VirtualMachine):
                        num_vms = num_vms + 1
                if len(hosts) < num_vms:
                    # Fail: More VMs requested than compute hosts 
                    # on rack.  Remove from this slice the sliver 
                    # objects created during this call to allocate 
                    # before returning an error struct
                    self.cleanup_slivers(slivers, slice_object)
                    code =  {'geni_code': constants.REQUEST_PARSE_FAILED}
                    error_output = \
                        "For OpenFlow controlled slice, limit of " + \
                        str(len(hosts)) + " VM's"
                    return {'code': code, 'value':'', 
                                'output':error_output}
        
            # Set the experimenter provider controller URL (if any)
            for link_object in slice_object.getNetworkLinks():
                link_name = link_object.getName()
                if link_name in controller_link_info:
                    controller_url_for_link = controller_link_info[link_name]
                    link_object.setControllerURL(controller_url_for_link)

            # Set expiration times on the allocated resources
            expiration = utils.min_expire(creds, 
                         self._max_alloc_time,
                         'geni_end_time' in options and options['geni_end_time'])
            for sliver in slivers :
                sliver.setExpiration(expiration)

            # Set expiration time on the slice itself
                slice_object.setExpiration(expiration);

            # Associate an external VLAN tag with every 
            # stitching link
#            print 'allocating external vlan'
            # Allocate external vlans and set them on the slivers
            is_v2_allocation = 'AM_API_V2' in options
            for link_sliver_object in slice_object.getNetworkLinks():
                success, error_string, error_code = \
                    self._stitching.allocate_external_vlan_tags(link_sliver_object, \
                                                                    rspec, is_v2_allocation)
                if not success:
                    self.cleanup_slivers(slivers, slice_object)
                    return {'code' : {'geni_code' : error_code}, 'value' : "",
                            'output' : error_string}

            # Associate an internal VLAN tag with every link 
            # that isn't already set by stitching
#            print 'allocating internal vlan'
            if not self.allocate_internal_vlan_tags(slice_object):
                self.cleanup_slivers(slivers, slice_object)
                error_string = "No more internal VLAN tags available"
                error_code = constants.VLAN_UNAVAILABLE
                return {'code' : {'geni_code' : error_code}, 'value' : "",
                        'output' : error_string}
 
            # Generate a manifest rspec
            slice_object.setRequestRspec(rspec)
            for sliver in slivers:
                sliver.setRequestRspec(rspec);
            agg_urn = self._aggregate_urn
            # At this point, we don't allocate VLAN's: they should already be allocated
            manifest, error_string, error_code =  \
                rspec_handler.generateManifestForSlivers(slice_object, \
                                                             slivers, True, \
                                                             False,
                                                             agg_urn, \
                                                             self._stitching)
            if error_code != constants.SUCCESS:
                self.cleanup_slivers(slivers, slice_object)
                return {'code' : {'geni_code' : error_code}, 'value' : "", 
                        'output' : error_string}

            slice_object.setManifestRspec(manifest)

            # Set the user urn for all new slivers
            all_slice_slivers = slice_object.getAllSlivers()
            for sliver_urn in all_slice_slivers:
                sliver = all_slice_slivers[sliver_urn]
                if not sliver.getUserURN():
                    sliver.setUserURN(user_urn)

            # Persist aggregate state
            self.persist_state()

            # Create a sliver status list for the slivers allocated by this call
            sliver_status_list = \
                utils.SliverList().getStatusOfSlivers(slivers)


            # Generate the return struct
            code = {'geni_code': constants.SUCCESS}
            result_struct = {'geni_rspec':manifest,
                             'geni_slivers':sliver_status_list}
            return {'code': code, 'value': result_struct, 'output': ''}
        

    def provision(self, slice_object, sliver_objects, creds, options) :
        """
            AM API V3 method.

            Provision the slivers listed in sliver_objects, if they have
            not already been provisioned.
        """
        if len(sliver_objects) == 0 :
            # No slivers specified: Return error message
            code = {'geni_code': constants.REQUEST_PARSE_FAILED}
            err_str = 'No slivers to be provisioned.'
            return {'code': code, 'value': '', 'output': err_str}

        # Make sure slivers have been allocated before we provision them.
        # Return an error if even one of the slivers has not been allocated
        for sliver in sliver_objects :
            if sliver.getAllocationState() != constants.allocated :
                # Found a sliver that has not been allocated.  Return with error.
                code = {'geni_code': constants.REQUEST_PARSE_FAILED}
                err_str = 'Slivers to be provisioned must have allocation state geni_allocated'
                return {'code': code, 'value': '', 'output': err_str}
                
        # See if the geni_users option has been set.  This option is used to
        # specify user accounts to be created on virtual machines that are
        # provisioned by this call
        if options.has_key('geni_users'):
            users = options['geni_users']
        else :
            users = list()
        
        # Lock this slice so nobody else can mess with it during provisioning
        with slice_object.getLock() :
            err_str = open_stack_interface.provisionResources(slice_object,
                                                              sliver_objects,
                                                              users, self)
            if err_str != None :
                # We failed to provision this slice for some reason (described
                # in err_str)
                code = {'geni_code': constants.OPENSTACK_ERROR}
                self.delete(slice_object, sliver_objects, options)        
                return {'code': code, 'value': '', 'output': err_str}
    
            # Set expiration times on the provisioned resources
            # Set expiration times on the allocated resources
            expiration = utils.min_expire(creds, self._max_lease_time,
                         'geni_end_time' in options and options['geni_end_time'])
            for sliver in sliver_objects :
                sliver.setExpiration(expiration)

            # Generate a manifest rpsec 
            req_rspec = slice_object.getRequestRspec()
            manifest, error_string, error_code =  \
                rspec_handler.generateManifestForSlivers(slice_object,
                                                         sliver_objects,
                                                         True,
                                                         False,
                                                         self._aggregate_urn,
                                                         self._stitching)

            if error_code != constants.SUCCESS:
                return {'code' : {'geni_code' : error_code}, 'value' : "", 
                        'output' : error_string}
    
            # Create a sliver status list for the slivers that were provisioned
            sliver_status_list = \
                utils.SliverList().getStatusOfSlivers(sliver_objects)

            # Persist new GramManager state
            self.persist_state()

            # Report the new slice to VMOC
            self.registerSliceToVMOC(slice_object)

            # Generate the return struct
            code = {'geni_code': constants.SUCCESS}
            result_struct = {'geni_rspec':manifest, \
                                 'geni_slivers':sliver_status_list}
            return {'code': code, 'value': result_struct, 'output': ''}
        

    def status(self, slice_object, slivers, options) :
        """
            AM API V3 method.

            Return the status of the specified slivers
        """
        # Lock this slice so nobody else can mess with it while we get status
        with slice_object.getLock() :
            open_stack_interface.updateOperationalStatus(slice_object)

            # Create a list with the status of the specified slivers
            sliver_status_list = \
                utils.SliverList().getStatusOfSlivers(slivers)
        
            # Generate the return stuct
            code = {'geni_code': constants.SUCCESS}
            result_struct = {'geni_urn':slice_object.getSliceURN(), \
                                 'geni_slivers':sliver_status_list}


            return {'code': code, 'value': result_struct, 'output': ''}
        

    def describe(self, slice_object, slivers, options) :
        """
            AM API V3 method.

            Describe the status of the resources allocated to this slice.
        """
        # Lock this slice so nobody else can mess with it while we get status
        with slice_object.getLock() :
            open_stack_interface.updateOperationalStatus(slice_object)

            # Get the status of the slivers
            sliver_status_list = \
                utils.SliverList().getStatusOfSlivers(slivers)

            # Generate the manifest to be returned
            manifest, error_string, error_code =  \
                rspec_handler.generateManifestForSlivers(slice_object, 
                                                         slivers, 
                                                         False, 
                                                         False,
                                                         self._aggregate_urn,
                                                         self._stitching)

            if error_code != constants.SUCCESS:
                return {'code' : {'geni_code' : error_code}, 'value' : "", 
                        'output' : error_string}

            # Generate the return struct
            code = {'geni_code': constants.SUCCESS}
            result_struct = {'geni_rspec': manifest,
                             'geni_urn':slice_object.getSliceURN(), 
                             'geni_slivers': sliver_status_list}

            ret_val = {'code': code, 'value': result_struct, 'output': ''}
            return ret_val


    # Perform operational action.
    # By the time this is called, we should know that the slivers
    # are in the right state to for the given action
    def performOperationalAction(self, slice_object, slivers, action, options) :
        """
            AM API V3 method.

            Support these actions:
                geni_start (boot if not_ready)
                geni_restart (reboot if ready)
                geni_stop (shutdown if ready)
        """
        ret_str = ""
        if action == 'delete_snapshot':
            ret_code, ret_str = open_stack_interface._deleteImage(options)
            sliver_status_list = utils.SliverList().getStatusOfSlivers(slivers)
            ret_val = {'code': {'geni_code': ret_code}, 'value': "", 'output': ret_str}
            GramImageInfo.refresh()
            return ret_val

        elif action == 'create_snapshot':
            if not options['snapshot_name'] or not options['vm_name']:
                ret_code = constants.REQUEST_PARSE_FAILED 
                ret_str = "Must specify vm_name and snapshot_name in output file"
            else:
                ret_code,ret_str = open_stack_interface._createImage(slivers,options) 
            ret_val = {'code': {'geni_code': ret_code}, 'value': "", 'output': ret_str}
            GramImageInfo.refresh()
            return ret_val

        elif action in ["geni_start", "geni_stop", "geni_restart"]:            
          ret_str = ""
          for sliver_object in slivers:
            # Only perform operational actions on VMs
            if not isinstance(sliver_object, VirtualMachine): continue

            # Perform operational action on VM within openstack
            ret = open_stack_interface._performOperationalAction(sliver_object, action,options)

            if not ret:
                ret_str += "Failed to perform " + action + " on " + sliver_object.getName() + "\n"
        else:
            ret_str = "Operation not supported"
       
        if not len(ret_str):
            code = {'geni_code': constants.SUCCESS}
        else:
            code = {'geni_code': constants.REQUEST_PARSE_FAILED}


        sliver_status_list = \
                utils.SliverList().getStatusOfSlivers(slivers)
        ret_val = {'code': code, 'value': sliver_status_list, 'output': ret_str}
        return ret_val

    def delete(self, slice_object, sliver_objects, options) :
        """
            AM API V3 method.

            Delete the specified sliver_objects.  All sliver_objecs are
            associated with the same slice_object.
        """
        config.logger.info('Delete called for slice %r' % \
                               slice_object.getSliceURN())

        # Lock this slice so nobody else can mess with it while we do the deletes
        with slice_object.getLock() :
            # Delete any slivers that have been provisioned
            # First find the sliver_objects that have been provisioned.
            # Provisioned slivers need their OpenStack resources deleted.  
            # Other slivers just need their allocation and operational states
            # changed.
            provisioned_slivers = []
            for sliver in sliver_objects :
                if sliver.getAllocationState() == constants.provisioned :
                    provisioned_slivers.append(sliver)
                else :
                    # Sliver has not been provisioned.  Just change its
                    # allocation and operational states
                    sliver.setAllocationState(constants.unallocated)
                    sliver.setOperationalState(constants.stopping)

            # Delete provisioned slivers
            success =  open_stack_interface.deleteSlivers(slice_object, 
                                                          provisioned_slivers)

            sliver_status_list = \
                utils.SliverList().getStatusOfSlivers(sliver_objects)

            # Remove deleted slivers from the slice
            for sliver in sliver_objects :
                slice_object.removeSliver(sliver)

            ### THIS CODE SHOULD BE MOVED TO EXPIRE WHEN WE ACTUALLY EXPIRE
            ### SLIVERS AND SLICES.  SLICES SHOULD BE DELETED ONLY WHEN THEY
            ### EXPIRE.  FOR NOW WE DELETE THEM WHEN ALL THEIR SLIVERS ARE 
            ### DELETED.
            if len(slice_object.getSlivers()) == 0 :
                open_stack_interface.expireSlice(slice_object)
                # Update VMOC
                self.registerSliceToVMOC(slice_object, False)
                # Remove slice from GRAM
                SliceURNtoSliceObject.remove_slice_object(slice_object.getSliceURN());

            # Free all stitching VLAN allocations
            for sliver in sliver_objects:
                self._stitching.deleteAllocation(sliver.getSliverURN())

            # Free all internal vlans back to pool
            for sliver in sliver_objects:
                if isinstance(sliver, NetworkLink):
                    tag = sliver.getVLANTag()
                    if self._internal_vlans.isAllocated(tag):
                        self._internal_vlans.free(tag)

            # Persist new GramManager state
            self.persist_state()

            # Generate the return struct
            code = {'geni_code': constants.SUCCESS}
            if success :
                return {'code': code, 'value': sliver_status_list,  'output': ''}
            else :
                return {'code':code, 
                        'value':sliver_status_list,
                        'output': 'Failed to delete one or more slivers'}


    def renew_slivers(self,slice_object, sliver_objects, creds, expiration_time, options):
        """
            AM API V3 method.

            Set the expiration time of the specified slivers to the specified
            value.  If the slice credentials expire before the specified
            expiration time, set sliver expiration times to the slice 
            credentials expiration time.
        """
        expiration = utils.min_expire(creds, self._max_lease_time,
                                      expiration_time)

        # Lock this slice so nobody else can mess with it while we renew
        with slice_object.getLock() :
            for sliver in sliver_objects :
                sliver.setExpiration(expiration)

            # Create a sliver status list for the slivers that were renewed
            sliver_status_list = \
                utils.SliverList().getStatusOfSlivers(sliver_objects)

            requested = utils._naiveUTC(dateutil.parser.parse(expiration_time))

            # If geni_extend_alap option provided, use the earlier           
            # of the requested time and max expiration as the expiration time
            if 'geni_extend_alap' in options and options['geni_extend_alap']:
                if expiration < requested:
                    slice_urn = slice_object.getSliceURN()
                    config.logger.info("Got geni_extend_alap: revising slice %s renew request from %s to %s" % (slice_urn, requested, expiration))
                requested = expiration

            if requested > expiration:
                config.logger.info('expiration time too long')
                code = {'geni_code':constants.REQUEST_PARSE_FAILED}
                return {'code':code, 'value':sliver_status_list, 'output':'ERROR: Requested sliver expiration is greater than either the slice expiration or the maximum lease time: ' + str(config.lease_expiration_minutes) + ' minutes'}

            code = {'geni_code': constants.SUCCESS}
            return {'code': code, 'value': sliver_status_list, 'output':''}



    def shutdown_slice(self, slice_urn):
        """
            AM API V3 method.
            
            Shutdown the slice.
        """
        # *** Ideally, we want shutdown to disable the slice by cutting off
        # network access or saving a snapshot of the images of running VM's
        # In the meantime, shutdown is just deleting the slice
        urns = [slice_urn]
        options = {}
        ret_val =  self.delete(urns, options);
        code = ret_val['code']
        output = ret_val['output']
        value = code == constants.SUCCESS
        return {'code':code, 'value':value, 'output':output}


    # Persist state to file based on current timestamp
    __persist_filename_format="%Y_%m_%d_%H_%M_%S"
    __recent_base_filename=None
    __base_filename_counter=0
    def persist_state(self):
        if not self._snapshot_directory: return
        start_time = time.time()
        base_filename = \
            time.strftime(GramManager.__persist_filename_format, time.localtime(start_time))
        counter = 0
        if base_filename==GramManager.__recent_base_filename:
            GramManager.__base_filename_counter = GramManager.__base_filename_counter + 1
            counter = GramManager.__base_filename_counter
        else:
            GramManager.__base_filename_counter=0
#        print "BFN %s RBFN %s COUNTER %d GMBFNC %d" % (base_filename, GramManager.__recent_base_filename, GramManager.__base_filename_counter, counter)
        GramManager.__recent_base_filename = base_filename
        filename = "%s/%s_%d.json" % (self._snapshot_directory, \
                                         base_filename, counter)
        GramManager.__recent_base_filename = base_filename
        Archiving.write_state(filename, self, SliceURNtoSliceObject._slices,
                               self._stitching)
        end_time = time.time()
        config.logger.info("Persisting state to %s in %.2f sec" % \
                               (filename, (end_time - start_time)))

    # Update VMOC about state of given slice (register or unregister)
    # Register both the control network and all data networks
    def registerSliceToVMOC(self, slice, register=True):
        if not config.vmoc_slice_autoregister: return

        slice_id = slice.getSliceURN()

        vlan_configs = []

        # Register/unregister control network
        # control_network_info = slice.getControlNetInfo()
        # if not control_network_info or \
        #         not control_network_info.has_key('control_net_vlan'):
        #     return

        # control_network_vlan = control_network_info['control_net_vlan']
        # control_net_config = \
        #     VMOCVLANConfiguration(vlan_tag=control_network_vlan, \
        #                               controller_url=None)
        # vlan_configs.append(control_net_config)

        # Register/unregister data networks
        for link in slice.getNetworkLinks():
            controller_url = link.getControllerURL()
            data_network_vlan = link.getVLANTag()
            if data_network_vlan is None: continue
            data_net_config = \
                VMOCVLANConfiguration(vlan_tag=data_network_vlan, \
                                          controller_url=controller_url)
            vlan_configs.append(data_net_config)

        slice_config=VMOCSliceConfiguration(slice_id=slice_id, \
                                                vlan_configs=vlan_configs)
        if register:
            VMOCClientInterface.register(slice_config)
        else:
            VMOCClientInterface.unregister(slice_config)



    # Resolve a set of URN's to a slice and set of slivers
    # Either:
    # It is a single slice URN 
    #     (return slice and associated sliver objects)
    # Or it is a set of sliver URN's  
    #     (return slice and slivers for these sliver URN's)
    # Returns a slice and a list of sliver objects    
    def decode_urns(self, urns):
        slice = None
        slivers = list()
        if len(urns) == 1 and \
                SliceURNtoSliceObject.get_slice_object(urns[0]) != None :
            # Case 1: This is a slice URN. 
            # Return slice and the urn's of the slivers
            slice_urn = urns[0]
            slice = SliceURNtoSliceObject.get_slice_object(slice_urn)
            slivers = slice.getSlivers().values()
        elif len(urns) > 0:
            # Case 2: This is a sliver URN.
            # Make sure they all belong to the same slice
            # And if so, return the slice and the sliver objects for these 
            # sliver urns
            sliver_urn = urns[0]
            slice = None
            for test_slice in SliceURNtoSliceObject.get_slice_objects() :
                if test_slice.getSlivers().has_key(sliver_urn):
                    slice = test_slice
                    break
            if slice:
                for sliver_urn  in urns:
                    if not slice.getSlivers().has_key(sliver_urn):
                        raise ApiErrorException(AM_API.BAD_ARGS, 
                                                "Decode_URNs: All sliver " + 
                                                "URN's must be part of same slice")
                    else:
                        sliver = slice.getSlivers()[sliver_urn]
                        slivers.append(sliver)
        return slice, slivers


    def expire_slivers(self):
        """
            Find and delete slivers that have expired.
        """
        # We walk through the list of slices.  For each slice we make a 
        # list of slivers that have expired.  If the slice has slivers that
        # have expired, we use the self.delete method to delete these slivers
        now = datetime.datetime.utcnow()
        for slice_object in SliceURNtoSliceObject.get_slice_objects():
            # Lock this slice so nobody else can mess with it while we expire
            # its slivers
            with slice_object.getLock() :
                slivers = slice_object.getSlivers()
                expired_slivers = list()
                for sliver in slivers.values():
                    if not sliver.getExpiration() or sliver.getExpiration() < now:
                        expired_slivers.append(sliver)
                if len(expired_slivers) != 0 :
                    self.delete(slice_object, expired_slivers, None)


    def list_flavors(self):
        return open_stack_interface._listFlavors()

    # See https://www.protogeni.net/trac/protogeni/wiki/RspecAdOpState
    def advert_header(self):
        header = '''<?xml version="1.0" encoding="UTF-8"?>
<rspec xmlns="http://www.geni.net/resources/rspec/3"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xsi:schemaLocation="%s"
       type="advertisement">'''
        return header

    # Restore state from snapshot specified in config
    def restore_state(self):
        if self._snapshot_directory is not None:
            if not os.path.exists(self._snapshot_directory):
                os.makedirs(self._snapshot_directory)
            # Use the specified one (if any)
            # Otherwise, use the most recent (if indicated)
            # Otherwise, no state to restore
#            print config.recover_from_most_recent_snapshot
            snapshot_file = None
            if config.recover_from_snapshot and \
                    config.recover_from_snapshot != "": 
                snapshot_file = config.recover_from_snapshot
            if not snapshot_file and config.recover_from_most_recent_snapshot:
                files = self.get_snapshots()
                if files and len(files) > 0:
                    snapshot_file = files[len(files)-1]
                config.logger.info("SNAPSHOT FILE : %s" % snapshot_file)
#                print 'snapshot file: '
#                print snapshot_file
            if snapshot_file is not None:
                config.logger.info("Restoring state from snapshot : %s" \
                                       % snapshot_file)
                SliceURNtoSliceObject._slices = \
                    Archiving.read_state(snapshot_file, self, self._stitching)
                # Restore the state of the VLAN pools
                # Go through all the network links and 
                # if the vlan tag is in the internal pool, allocate it

                for slice_urn, slice_obj in SliceURNtoSliceObject._slices.items():
                    for network_link in slice_obj.getNetworkLinks():
                        vlan_tag = network_link.getVLANTag()
                        if vlan_tag and vlan_tag in self._internal_vlans.getAllVLANs():
#                            config.logger.info("Restored internal VLAN %d" % vlan_tag)
                            self._internal_vlans.allocate(vlan_tag)

                config.logger.info("Restored %d slices" % \
                                       len(SliceURNtoSliceObject._slices))

    # Clean up expired slices periodically
    def periodic_cleanup(self):
        token_table_user = 'keystone'
        token_table_database = 'keystone'
        token_retention_window_days = 1
        while True:
            cmd = None
            try:
                config.logger.info("Cleaning up expired slivers")
                cmd = "mysql -u%s -p%s -h%s %s -e 'DELETE FROM token WHERE NOT DATE_SUB(CURDATE(),INTERVAL %d DAY) <= expires'" % \
                    (token_table_user, config.mysql_password, 
                     config.control_host_addr, token_table_database, 
                     token_retention_window_days)
            except Exception, e:
                print e
#            print cmd
            os.system(cmd)

            cmd = "openstack project list"
            output = open_stack_interface._execCommand(cmd)
            output_fields = open_stack_interface._parseTableOutput(output)
            tenant_uuids =  output_fields['ID']
            print "TENANT_UUIDS = %s" % tenant_uuids
            try:
                config.logger.info("Cleaning up dangling secgrps")
                uuids_expr =  ",".join("'" + tenant_uuid + "'" \
                                           for tenant_uuid in tenant_uuids)

                for table_name in ['securitygrouprules', 'securitygroups']:
                    cmd = "mysql -u%s -p%s -h%s %s -e %sDELETE from %s where tenant_id not in (%s)%s" % \
                        (config.network_user, config.mysql_password,
                         config.control_host_addr, config.network_database,
                         '"', table_name, uuids_expr, '"')
                    print cmd
                    #RRH - have to figure out why tables don't exist in the neutron database - os.system(cmd)
            except Exception, e:
                print e
                
            self.expire_slivers()
            time.sleep(3000)

    # Allocate internal VLAN tags to all links for which the tag is not
    # yet set (by stitching)
    def allocate_internal_vlan_tags(self, slice_object):
        for link_sliver in slice_object.getNetworkLinks():
            data_network_vlan = link_sliver.getVLANTag()
            if data_network_vlan is None: 
                success, tag = self._internal_vlans.allocate(None)
                if not success: return False
                link_sliver.setVLANTag(tag)
        return True


    # Remove old snapshots, keeping only last config.snapshot_maintain_limit
    def prune_snapshots(self):
        files = self.get_snapshots()
        if files and len(files) > config.snapshot_maintain_limit:
            files_to_remove = files[0:len(files)-config.snapshot_maintain_limit-1]
            for file in files_to_remove:
                os.unlink(file)

    # Return list of files in config.gam_snapshot_directory  in time
    # ascending order
    def get_snapshots(self):
        files = None
        if self._snapshot_directory:
            dir = self._snapshot_directory
            files = [os.path.join(dir, s) for s in os.listdir(dir)
                     if os.path.isfile(os.path.join(dir, s))]
            files.sort(key = lambda s: os.path.getmtime(s))
        return files

    # Compute the UUIDs of OpenStack objects for all slices
    # Return dictionary of 'vm_uuids', 'net_uuids', 'router_uuids', 
    #    'subnet_uuids' indexed by tenant_uuid
    def get_all_slice_info(self):
        result = {}

        for slice_urn, slice_object in SliceURNtoSliceObject._slices.items():
            tenant_uuid = slice_object.getTenantUUID()
            result[tenant_uuid] = {}

            tenant_router_uuid = slice_object.getTenantRouterUUID()
            result[tenant_uuid]['router_uuids'] = [tenant_router_uuid]

            tenant_admin_name, tenant_admin_pwd, tenant_admin_uuid = \
                slice_object.getTenantAdminInfo()
            result[tenant_uuid]['user_uuids'] = [tenant_admin_uuid]

            result[tenant_uuid]['net_uuids'] = []
            result[tenant_uuid]['subnet_uuids'] = []
            result[tenant_uuid]['vm_uuids'] = []
            
            for network_link in slice_object.getNetworkLinks():
                net_uuid = network_link.getNetworkUUID()
                if net_uuid not in result[tenant_uuid]['net_uuids']:
                    result[tenant_uuid]['net_uuids'].append(net_uuid)
                subnet_uuid = network_link.getSubnetUUID()
                if subnet_uuid not in result[tenant_uuid]['subnet_uuids']:
                    result[tenant_uuid]['subnet_uuids'].append(subnet_uuid)

            for vm in slice_object.getVMs():
                vm_uuid = vm.getUUID()
                result[tenant_uuid]['vm_uuids'].append(vm_uuid)

        return result


    # Reconcile state of gram manager slices/slivers with the resources
    # Currently defined in OpenStack
    # If any resources in GRAM of a given slice no longer exist in OpenStack
    # Delete the slice
    def reconcile_state(self):
#        print "RECONCILING...."
        os_info = open_stack_interface.get_all_tenant_info()
#        print "OS_INFO   = %s" % os_info
        gram_info = self.get_all_slice_info()
#        print "GRAM_INFO = %s" % gram_info

        # Compare the two sets of tagged UUIDS
        # If gram has some slice that OS doesn't or the 
        # gram slice has some UUIDs that OS doesn't have or
        # OS slice has some UUIDS that GRAM doesn't have, delete slice
        # from GRAM and OS
        tenants_to_delete = []
        for tenant_id, tenant_data in gram_info.items():
            # Is this a slice in GRAM but not in OpenStack
            if not tenant_id in os_info:
                tenants_to_delete.append(tenant_id)
            else:
                for key, gram_data in tenant_data.items():
                    # Is this a slice with the same uuid type but not same
                    # entries
                    if key in os_info[tenant_id]:
                        os_data = os_info[tenant_id][key]
                        gram_data.sort()
                        os_data.sort()
                        if cmp(gram_data, os_data) != 0:
                            tenants_to_delete.append(tenant_id)
                            break
                    else:
                        # This is a slice with some key in GRAM not in OS
                        tenants_to_delete.append(tenant_id)
                        break

        if len(tenants_to_delete) > 0:
            config.logger.info("OpenStack and GRAM-internal representations of these tenants are inconsistent: deleting from OpenStack and GRAM %s " % tenants_to_delete)
            for slice_urn, slice_object in SliceURNtoSliceObject._slices.items():
                tenant_uuid = slice_object.getTenantUUID()
                if tenant_uuid in tenants_to_delete:
                    slice_slivers = slice_object.getSlivers().values()
                    config.logger.info("Deleting Slice URN = %s" % slice_urn)
                    self.delete(slice_object, slice_slivers, {})



    def __del__(self) :
        config.logger.info('In destructor')
        # open_stack_interface.cleanup(None, None)

    def errorResult(self, code, output, am_code=None):
        code_dict = dict(geni_code=code,
                         am_type=self._am_type)
        if am_code is not None:
            code_dict['am_code'] = am_code
        return dict(code=code_dict,
                    value="",
                    output=output)
