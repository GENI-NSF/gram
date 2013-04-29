
import datetime
import dateutil
import os
import getpass
import signal
import time

import config
import constants
from resources import Slice, VirtualMachine
import rspec_handler
import open_stack_interface
import utils
import Archiving
import threading

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
    def __init__(self) :
        open_stack_interface.init() # OpenStack related initialization

        # Set up a signal handler to clean up on a control-c
        # signal.signal(signal.SIGINT, open_stack_interface.cleanup)

        self._snapshot_directory = None
        if config.gram_snapshot_directory:
            self._snapshot_directory = \
                config.gram_snapshot_directory + "/" + getpass.getuser()

        # Set max lease renewal to 7 days
        self._max_lease = datetime.timedelta(minutes=7*24*60) 

        # Client interface to VMOC - update VMOC on current
        # State of all slices and their associated 
        # network VLAN's and controllers
        if config.vmoc_slice_autoregister:
            VMOCClientInterface.startup()
            config.logger.info("Started VMOC Client Interface from gram manager")

        # Recover state from snapshot, if configured to do so
        self.restore_state()

        # If any slices restored from snapshot, report to VMOC
        with SliceURNtoSliceObject._lock:
            for slice in SliceURNtoSliceObject._slices:
                self.registerSliceToVMOC(slice)
        
        # Remove extraneous snapshots
        self.prune_snapshots()


    def allocate(self, slice_urn, creds, rspec, options) :
        """
            Request reservation of GRAM resources.  We assume that by the 
            time we get here the caller's credentials have been verified 
            by the gcf framework (see am3.py).

            Returns None if successful.
            Returns an error string on failure.
        """
        config.logger.info('Allocate called for slice %r' % slice_urn)


        # Check if we already have slivers for this slice
        slice_object = SliceURNtoSliceObject.get_slice_object(slice_urn)
        if slice_object == None :
            # This is a new slice at this aggregate.  Create Slice object 
            # and add it the list of slices at this AM
            slice_object = Slice(slice_urn)
            SliceURNtoSliceObject.set_slice_object(slice_urn, slice_object)

        # Parse the request rspec.  Get back any error message from parsing
        # the rspec and a list of slivers created while parsing
        # Also OF controller, if any
        err_output, slivers, controller_url = \
            rspec_handler.parseRequestRspec(slice_object, rspec)

        if err_output != None :
            # Something went wrong.  First remove from the slice any sliver
            # objects created while parsing the bad rspec
            for sliver_object in slivers :
                slice_object.removeSliver(sliver_object)
                
            # Return an error struct.
            code = {'geni_code': constants.REQUEST_PARSE_FAILED}
            return {'code': code, 'value': '', 'output': err_output}


        # If we're associating an OpenFlow controller to this slice, 
        # Each VM must go on its own host. If there are more nodes
        # than hosts, we fail
        if controller_url:
            hosts = open_stack_interface._listHosts('compute')
            num_vms = 0
            for sliver in slivers:
                if isinstance(sliver, VirtualMachine):
                    num_vms = num_vms + 1
            if len(hosts) < num_vms:
                code = {'geni_code': constants.REQUEST_PARSE_FAILED}
                error_output = \
                    "For OpenFlow controlled slice, limit of " + \
                    str(len(hosts)) + " VM's"
                return {'code': code, 'value':'', 'output':error_output}
        
        # Set the experimenter provider controller URL (if any)
        slice_object.setControllerURL(controller_url)

        # Set expiration times on the allocated resources
        utils.AllocationTimesSetter(slice_object, creds, \
                                        ('geni_end_time' in options \
                                             and \
                                             options['geni_end_time']))

        # Generate a manifest rpsec
        slice_object.setRequestRspec(rspec)
        manifest =  rspec_handler.generateManifest(slice_object, rspec)
        slice_object.setManifestRspec(manifest)

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
            Provision the slivers listed in sliver_objects, if they have
            not already been provisioned.
        """
        # See if the geni_users option has been set.  This option is used to
        # specify user accounts to be created on virtual machines that are
        # provisioned by this call
        if options.has_key('geni_users'):
            users = options['geni_users']
        else :
            users = list()

        
        err_str = open_stack_interface.provisionResources(slice_object,
                                                          sliver_objects,
                                                          users)

        #err_str = open_stack_interface.provisionResources(slice_object, users)
        if err_str != None :
            # We failed to provision this slice for some reason (described
            # in err_str)
            code = {'geni_code': constants.OPENSTACK_ERROR}
            return {'code': code, 'value': '', 'output': err_str}
            
        # Set expiration times on the provisioned resources
        utils.ProvisionTimesSetter(slice_object, creds, \
                                       ('geni_end_time' in options \
                                            and options['geni_end_time']))

        # Generate a manifest rpsec 
        req_rspec = slice_object.getRequestRspec()
        manifest = rspec_handler.generateManifest(slice_object, req_rspec)
    
        # Save the manifest in the slice object.  THIS IS TEMPORARY.  WE
        # SHOULD BE GENERATING THE SLICE MANIFEST AS NEEDED
        slice_object.setManifestRspec(manifest)

        # Create a sliver status list for the slivers in this slice
        sliver_status_list = utils.SliverList().getStatusAllSlivers(slice_object)

        # Persist new GramManager state
        self.persist_state()

        # Report the new slice to VMOC
        self.registerSliceToVMOC(slice_object)

        # Generate the return struct
        code = {'geni_code': constants.SUCCESS}
        result_struct = {'geni_rspec':manifest, 'geni_slivers':sliver_status_list}
        return {'code': code, 'value': result_struct, 'output': ''}
        

    def describe(self, slice_urn, options) :
        """
            Describe the status of the resources allocated to this slice.
        """

        # Find the slice object
        slice_object = SliceURNtoSliceObject.get_slice_object(slice_urn)
        if slice_object == None :
            config.logger.error('Asked to describe unknown slice %s' % urns[0])
            err_output = 'Search for slice %s failed' % slice_urn
            code = {'geni_code': constants.UNKNOWN_SLICE}
            return {'code': code, 'value': '', 'output': err_output}

        open_stack_interface.updateOperationalStatus(slice_object)

        sliver_stat_list = utils.SliverList()
        sliver_list = sliver_stat_list.getStatusAllSlivers(slice_object)

        # Generate the return struct
        code = {'geni_code': constants.SUCCESS}
        result_struct = {'geni_rspec': slice_object.getManifestRspec(), \
                             'geni_slivers': sliver_list}

        ret_val = {'code': code, 'value': result_struct, 'output': ''}

        return ret_val


    def delete(self, urns, options) :
        """
            Delete all resources held by a slice.  At this time we do 
            not support deletion of individual slivers.
        """
        config.logger.info('Delete called for slice %r' % urns)

        slice_object = SliceURNtoSliceObject.get_slice_object(urns[0])
        if slice_object == None :
            config.logger.error('Asked to delete unknown slice %s' % urns[0])
            err_output = 'Search for slice %s failed' % slice_urn
            code = {'geni_code': constants.UNKNOWN_SLICE}
            return {'code': code, 'value': '', 'output': err_output}

        # We do have the slice.  Delete all resources held by the slice
        sliver_status_list = \
            open_stack_interface.deleteAllResourcesForSlice(slice_object)

        # Remove slice from list of known slices
        SliceURNtoSliceObject.remove_slice_object(urns[0])

        # Persist new GramManager state
        self.persist_state()

        # Update VMOC
        self.registerSliceToVMOC(slice_object, False)

        # Generate the return struct
        code = {'geni_code': constants.SUCCESS}
        return {'code': code, 'value': sliver_status_list,  'output': ''}

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
        Archiving.write_slices(filename, SliceURNtoSliceObject._slices)
        end_time = time.time()
        config.logger.info("Persisting state to %s in %.2f sec" % \
                               (filename, (end_time - start_time)))

    # Update VMOC about state of given slice (register or unregister)
    # Register both the control network and all data networks
    def registerSliceToVMOC(self, slice, register=True):
        if not config.vmoc_slice_autoregister: return

        slice_id = slice.getSliceURN()
        controller_url = slice.getControllerURL()

        vlan_configs = []

        # Register/unregister control network
        control_network_info = slice.getControlNetInfo()
        if not control_network_info or \
                not control_network_info.has_key('control_net_vlan'):
            return

        control_network_vlan = control_network_info['control_net_vlan']
        control_net_config = \
            VMOCVLANConfiguration(vlan_tag=control_network_vlan, \
                                      controller_url=None)
        vlan_configs.append(control_net_config)

        # Register/unregister data networks
        for link in slice.getNetworkLinks():
            data_network_vlan = link.getVLANTag()
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
        expired = list()
        now = datetime.datetime.utcnow()
        for slice in SliceURNtoSliceObject.get_slice_objects():
            slivers = slice.getSlivers()
            for sliver in slivers.values():
                config.logger.debug('Checking sliver %s (expiration = %r) at %r', 
                                   sliver.getSliverURN(), \
                                        sliver.getExpiration(), now)
                if sliver.getExpiration() < now:
                    config.logger.debug('Expiring sliver %s (expire=%r) at %r', 
                                        sliver.getSliverURN(), \
                                            sliver.getExpiration(), now)
                    expired.append(sliver)
            config.logger.info('Expiring %d slivers', len(expired))
        for sliver in expired:
            slice = sliver.getSlice()
            slice_urn = slice.getSliceURN()
            slice.removeSliver(sliver)


    def renew_slivers(self, slivers, creds, expiration_time):
        urns = [sliver.getSliverURN() for sliver in slivers]
        config.logger.info('Renew(%r, %r)' % (urns, expiration_time))
        
        
        now = datetime.datetime.utcnow()
        expires = [self._naiveUTC(c.expiration) for c in creds]
        expires.append(now + self._max_lease)
        print str(expires)
        expiration = min(expires)
        requested = dateutil.parser.parse(str(expiration_time))
        requested = self._naiveUTC(requested)
        if requested > expiration:
            # Fail the call: the requested expiration exceeds the slice expir.
            msg = ("Out of range: Expiration %s is out of range" + 
                   " (past last credential expiration of %s).") % \
            (expiration_time, expiration)
            config.logger.info(msg)
            return self.errorResult(constants.OUT_OF_RANGE, msg)

        elif requested < now:
            msg = (("Out of range: Expiration %s is out of range" + 
                    " (prior to now %s)") % (expiration_time, now.isoformat()))
            config.logger.error(msg)
            return self.errorResult(constants.OUT_OF_RANGE, msg)

        else:
            for sliver in slivers:
                sliver.setExpiration(requested)

        code = {'geni_code':constants.SUCCESS}
        sliver_status_list = utils.SliverList()
        for sliver in slivers: sliver_status_list.addSliver(sliver)
        return {'code':code, \
                    'value':sliver_status_list.getSliverStatusList(), \
                    'output':''}

    def shutdown_slice(self, slice_urn):
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
            snapshot_file = None
            if config.recover_from_snapshot and \
                    config.recover_from_snapshot != "": 
                snapshot_file = config.recover_from_snapshot
            if not snapshot_file and config.recover_from_most_recent_snapshot:
                files = self.get_snapshots()
                if files and len(files) > 0:
                    snapshot_file = files[len(files)-1]

            if snapshot_file is not None:
                config.logger.info("Restoring state from snapshot : %s" \
                                       % snapshot_file)
                SliceURNtoSliceObject._slices = Archiving.read_slices(snapshot_file)
                config.logger.info("Restored %d slices" % \
                                       len(SliceURNtoSliceObject._slices))


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


    def _naiveUTC(self, dt):
        """Converts dt to a naive datetime in UTC.

        if 'dt' has a timezone then
        convert to UTC
        strip off timezone (make it "naive" in Python parlance)
        """
        if dt.tzinfo:
            tz_utc = dateutil.tz.tzutc()
            dt = dt.astimezone(tz_utc)
            dt = dt.replace(tzinfo=None)
        return dt
