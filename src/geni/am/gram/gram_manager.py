
import signal

import config
from resources import Slice
import rspec_handler
import open_stack_interface
import utils


class GramManager :
    """
        Only one instances of this class is created.
    """
    _slices = {}      # Slice objects at this aggregate, indexed by slice urn

    def __init__(self) :
        # open_stack_interface.init() # OpenStack related initialization

        # Set up a signal handler to clean up on a control-c
        # signal.signal(signal.SIGINT, open_stack_interface.cleanup)
        return
        

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
        if slice_urn in GramManager._slices :
            # This is a request to add additional resources to this slice.
            # Feature not supported at this time.
            config.logger.error('Cannot call allocate while holding slivers');
            error_output = 'Slice already has slivers at this aggregate.  Delete the slice before calling allocate again'

            # Create and return an error struct
            code = {'geni_code': config.SLICE_ALREADY_EXISTS}
            return {'code': code, 'value': '', 'output': error_output}

        # This is a new slice at this aggregate.  Create Slice object and add
        # it the list of slices at this AM
        geni_slice = Slice(slice_urn)
        GramManager._slices[slice_urn] = geni_slice

        # Parse the request rspec
        err_output = rspec_handler.parseRequestRspec(geni_slice, rspec)
        if err_output != None :
            # Something went wrong.  Return an error struct.
            code = {'geni_code': config.REQUEST_PARSE_FAILED}
            return {'code': code, 'value': '', 'output': err_output}

        # Set expiration times on the allocated resources
        utils.AllocationTimesSetter(geni_slice, creds, \
                                        ('geni_end_time' in options \
                                             and \
                                             options['geni_end_time']))

        # Generate a manifest rpsec
        geni_slice.setRequestRspec(rspec)
        manifest, sliver_list = \
            rspec_handler.generateManifest(geni_slice, rspec)

        # Generate the return struct
        code = {'geni_code': config.SUCCESS}
        result_struct = {'geni_rspec': manifest, 'geni_slivers': sliver_list}
        return {'code': code, 'value': result_struct, 'output': ''}
        

    def provision(self, slice_urn, creds, options) :
        """
            For now we provision all resources allocated by a slice.  In the
            future we'll have to provision individual slivers.
        """
        # Find the slice object for this slice
        if slice_urn not in GramManager._slices :
            #  Unknown slice.  Return error message
            err_output = 'Search for slice %s failed' % slice_urn
            code = {'geni_code': config.UNKNOWN_SLICE}
            return {'code': code, 'value': '', 'output': err_output}
        geni_slice = GramManager._slices[slice_urn]    

        # Provision OpenStack Resources
        if options.has_key('geni_users'):
            users = options['geni_users']
        else :
            users = list()
        open_stack_interface.provisionResources(geni_slice, users)

        # Set expiration times on the provisioned resources
        utils.ProvisionTimesSetter(geni_slice, creds, \
                                       ('geni_end_time' in options \
                                            and options['geni_end_time']))

        # Generate a manifest rpsec
        req_rspec = geni_slice.getRequestRspec()
        manifest, sliver_list = rspec_handler.generateManifest(geni_slice,
                                                               req_rspec)
    
        # Generate the return struct
        code = {'geni_code': config.SUCCESS}
        result_struct = {'geni_rspec': manifest, 'geni_slivers': sliver_list}
        return {'code': code, 'value': result_struct, 'output': ''}
        

    def delete(self, urns, options) :
        """
            Delete all resources held by a slice.  At this time we do 
            not support deletion of individual slivers.
        """
        config.logger.info('Delete called for slice %r' % urns)

        if urns[0] not in GramManager._slices :
            config.logger.error('Asked to delete unknown slice %s' % urns[0])
            err_output = 'Search for slice %s failed' % slice_urn
            code = {'geni_code': config.UNKNOWN_SLICE}
            return {'code': code, 'value': '', 'output': err_output}

        # We do have the slice.  Delete all resources held by the slice
        slice_object = GramManager._slices[urns[0]]
        sliver_status_list = \
            open_stack_interface.deleteAllResourcesForSlice(slice_object)

        # Remove slice from list of known slices
        del GramManager._slices[urns[0]]    

        # Generate the return struct
        code = {'geni_code': config.SUCCESS}
        return {'code': code, 'value': sliver_status_list,  'output': ''}


    def __del__(self) :
        print ('In destructor')
        # open_stack_interface.cleanup(None, None)

