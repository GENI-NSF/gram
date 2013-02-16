
import logging

# OpenStack related configuration
#default_VM_flavor = 'm1.smaller'  
default_VM_flavor = 'm1.tiny'  

#default_OS_image = 'cirros-0.3-x86_64'
#default_OS_type = 'Linux'
#default_OS_version = '0.3'

#default_OS_image = 'cirros-4nic'
#default_OS_type = 'Linux'
#default_OS_version = '0.3'

#default_OS_image = 'f17-x86_64-openstack-sda'
#default_OS_type = 'Linux'
#default_OS_version = '17'

#default_OS_image = 'ubuntu-12.04'
#default_OS_image = 'ubuntu-12.04-2nic'
#default_OS_image = 'ubuntu-2nic-wkey'
default_OS_image = 'cirros-2nic-x86_64'
default_OS_type = 'Linux'
default_OS_version = '12'

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
notready = 'geni_notready'
configuring = 'geni_configuring'
ready = 'geni_ready'
failed = 'geni_failed'


# Error codes returned by this aggregate manager
# GENI standard codes.
SUCCESS = 0
REQUEST_PARSE_FAILED = 1        # aka BADARGS
UNKNOWN_SLICE = 12              # aka SEARCHFAILED
UNSUPPORTED = 13                
SLICE_ALREADY_EXISTS = 17       # aka ALREADYEXISTS
OUT_OF_RANGE = 19               # typically for time mismatches

# GRAM specific codes

# Aggregate Manager software related configuration
logger = logging.getLogger('gcf.am3.gram')

# Parameters regarding archiving/restoration of GRAM aggregste state
gram_snapshot_directory = '/etc/gram/snapshots' # Directory of snapshots
recover_from_snapshot = None # Specific file from which to recover 
recover_from_most_recent_snapshot = True # Should we restore from most recent
snapshot_maintain_limit = 10 # Remove all snapshots earlier than this #

# GRAM AM URN (Component ID of AM)
gram_am_urn = ''

# PORT on which to communicate with compute_node_interace
compute_node_interface_port = 9501

# PORT on which to communicate to VMOC interface manager
vmoc_interface_port = 7001

# Should GRAM automatically register slices with VMOC?
vmoc_slice_autoregister = True # Set to False to disable GRAM/VMOC interface

# Variables for VMOC/GRAM switch behavior/configuration
vmoc_set_vlan_on_untagged_packet_out = False
vmoc_set_vlan_on_untagged_flow_mod = True
vmoc_accept_clear_all_flows_on_startup = True
