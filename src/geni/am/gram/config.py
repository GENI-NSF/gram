
import logging

# OpenStack related configuration
default_VM_flavor = 'm1.small'  
default_OS_image = 'cirros-0.3-x86_64'

tenant_admin_pwd = 'sliceMaster:-)'  # Password for the tenant's admin user
                                  # account

# GENI interface related configuration
default_execute_shell = 'sh'   # default shell to use for use by execute
                               # services specified in the request rspec
sliver_urn_prefix = 'urn:publicid:IDN+gram+sliver+'
vm_urn_prefix = sliver_urn_prefix + 'vm+'
interface_urn_prefix = sliver_urn_prefix + 'interface+'
link_urn_prefix = sliver_urn_prefix + 'link+'

allocation_expiration_time =  10 * 60 # allocations expire in 10 mins

# Allocation states for slivers
unallocated = 'geni_unallocated'
allocated = 'geni_allocated'
provisioned = 'geni_provisioned'

# Operational states for slivers
pending_allocation = 'geni_pending_allocation'
ready = 'geni_ready'
failed = 'geni_failed'


# Error codes returned by this aggregate manager
SUCCESS = 0    # This is a GENI standard
SLICE_ALREADY_EXISTS =  100
REQUEST_PARSE_FAILED = 200

# Aggregate Manager software related configuration
logger = logging.getLogger('gcf.am3.gram')

