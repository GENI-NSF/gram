
import config
from Resources import Slice
import rspec_handler
import open_stack_interface

slices = {}                # Collection of slice objects at this aggregate, 
                           # indexed by slice urn

def allocate(slice_urn, rspec, options) :
    """
        Request reservation of GRAM resources.  We assume that by the time we
        get here the caller's credentials have been verified by the gcf 
        framework (see am3.py).

        Returns None if successful.
        Returns an error string on failure.
    """
    config.logger.info('Allocate called for slice %r' % slice_urn)

    # Check if we already have slivers for this slice
    if slice_urn in slices :
        # This is a request to add additional resources to this slice.  Not
        # supported at this time.
        config.logger.error('Cannot call allocate while holding slivers');
        error_output = 'Slice already has slivers at this aggregate.  Delete the slice before calling allocate again'

        # Create and return an error struct
        code = {'geni_code': config.SLICE_ALREADY_EXISTS}
        return {'code': code, 'value': '', 'output': error_output}

    # This is a new slice at this aggregate.  Create Slice object and add
    # it the list of slices at this AM
    geni_slice = Slice(slice_urn)
    slices[slice_urn] = geni_slice

    # Parse the request rspec
    err_output = rspec_handler.parseRequestRspec(geni_slice, rspec)
    if err_output != None :
        # Something went wrong.  Return an error struct.
        code = {'geni_code': config.REQUEST_PARSE_FAILED}
        return {'code': code, 'value': '', 'output': err_output}

    # Assign resources per this request
    open_stack_interface.assignResources(geni_slice)

    # Generate a manifest rpsec
    manifest, sliver_list = rspec_handler.generateManifest(geni_slice, rspec)

    # Generate the return struct
    code = {'geni_code': config.SUCCESS}
    result_struct = {'geni_rspec': manifest, 'geni_slivers': sliver_list}
    return {'code': code, 'value': result_struct, 'output': ''}
        

def delete(urns, options) :
    """
        Delete all resources held by a slice.  At this time we do not support
        deletion of individual slivers.
    """
    config.logger.info('Delete called for slice %r' % urns)

    if urns[0] in slices :
        open_stack_interface.deleteAllResourcesForSlice(slices[urns[0]])
        del slices[urns[0]]    # 
    else :
        config.logger.error('Asked to delete unknown slice %s' % urns[0])
    

