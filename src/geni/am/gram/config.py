
import logging

# OpenStack related configuration
default_VM_flavor = 'm1.small'  
default_OS_image = 'cirros-0.3-x86_64'

control_net_name = 'GRAM-controlNet'
control_net_ip = '172.16.0.0/12'

external_router_name = 'externalRouter'

tenant_admin_pwd = 'sliceMaster:-)'  # Password for the tenant's admin user
                                  # account


# GENI interface related configuration
default_execute_shell = 'sh'   # default shell to use for use by execute
                               # services specified in the request rspec
sliver_urn_prefix = 'urn:publicid:IDN+gram+sliver+'
vm_urn_prefix = sliver_urn_prefix + 'vm+'
interface_urn_prefix = sliver_urn_prefix + 'interface+'
link_urn_prefix = sliver_urn_prefix + 'link+'

allocation_expiration_minutes =  10      # allocations expire in 10 mins
lease_expiration_minutes =  7 * 24 * 60  # resources can be leased for 7 days

# Allocation states for slivers
unallocated = 'geni_unallocated'
allocated = 'geni_allocated'
provisioned = 'geni_provisioned'

# Operational states for slivers
pending_allocation = 'geni_pending_allocation'
ready = 'geni_ready'
failed = 'geni_failed'


# Error codes returned by this aggregate manager
# GENI standard codes.
SUCCESS = 0
REQUEST_PARSE_FAILED = 1        # aka BADARGS
UNKNOWN_SLICE = 12              # aka SEARCHFAILED
SLICE_ALREADY_EXISTS = 17       # aka ALREADYEXISTS

# GRAM specific codes

# Aggregate Manager software related configuration
logger = logging.getLogger('gcf.am3.gram')

