#!/bin/sh
#
# Keystone basic configuration 

# Mainly inspired by https://github.com/openstack/keystone/blob/master/tools/sample_data.sh

# Modified by Bilel Msekni / Institut Telecom
#
# Support: openstack@lists.launchpad.net
# License: Apache Software License (ASL) 2.0
#

export CONTROL_HOST=boscontroller
#need to edit this with what is in keystone.conf for admin_token
export OS_SERVICE_TOKEN="ADMIN"
export OS_SERVICE_ENDPOINT="http://${CONTROL_HOST}:35357/v2.0"
export OS_TENANT_NAME=admin
export OS_USER_NAME=admin
export OS_PASSWORD=rrh_jn_db
export OS_AUTH_URL="http://${CONTROL_HOST}:35357/v2.0"
export OS_REGION=regionOne
export OS_EMAIL=admin@domain.com
export OS_SERVICE_PASSWORD="ADMIN"

# Tenants
keystone tenant-create --name admin --description "Admin Tenant"
keystone tenant-create --name service --description "Service Tenant"


# Users
keystone user-create --name admin --pass $OS_PASSWORD --email $OS_EMAIL


# Roles
keystone role-create --name admin

# Add Roles to Users in Tenants
keystone user-role-add --user admin --tenant admin --role admin 

# Configure service users/roles
keystone user-create --name nova --pass $OS_SERVICE_PASSWORD 
keystone user-role-add --user nova --tenant service  --role admin

keystone user-create --name glance --pass $OS_SERVICE_PASSWORD 
keystone user-role-add --user glance --tenant service  --role admin

keystone user-create --name neutron --pass $OS_SERVICE_PASSWORD 
keystone user-role-add --user neutron --tenant service  --role admin

# Create Services and Endpoints
keystone service-create --name keystone --type identity --description 'OpenStack Identity'
keystone endpoint-create --service-id $(keystone service-list | awk '/ identity / {print $2}') --publicurl 'http://'"$CONTROL_HOST"':5000/v2.0' --adminurl 'http://'"$CONTROL_HOST"':35357/v2.0' --internalurl 'http://'"$CONTROL_HOST"':5000/v2.0' --region $OS_REGION 

keystone service-create --name glance --type image --description 'OpenStack Image Service'
keystone endpoint-create --service-id $(keystone service-list | awk '/ image / {print $2}') --publicurl 'http://'"$CONTROL_HOST"':9292/' --adminurl 'http://'"$CONTROL_HOST"':9292/' --internalurl 'http://'"$CONTROL_HOST"':9292/' --region $OS_REGION 

keystone service-create --name nova --type compute --description 'OpenStack Compute Service'
keystone endpoint-create --service-id $(keystone service-list | awk '/ compute / {print $2}') --publicurl 'http://'"$CONTROL_HOST"':8774/v2/$(tenant_id)s' --adminurl 'http://'"$CONTROL_HOST"':8774/v2/$(tenant_id)s' --internalurl 'http://'"$CONTROL_HOST"':8774/v2/$(tenant_id)s' --region $OS_REGION 

keystone service-create --name neutron --type network --description 'OpenStack Networking service'
keystone endpoint-create --service-id $(keystone service-list | awk '/ network / {print $2}') --publicurl 'http://'"$CONTROL_HOST"':9696/' --adminurl 'http://'"$CONTROL_HOST"':9696/' --internalurl 'http://'"$CONTROL_HOST"':9696/' --region $OS_REGION 
