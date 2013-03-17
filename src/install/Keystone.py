from GenericInstaller import GenericInstaller
from Configuration import Configuration

class Keystone(GenericInstaller):

    # Return a list of command strings for installing this component
    def installCommands(self, params):

        # Pull parameters from configuration
        openstack_user = params[Configuration.ENV.OS_USERNAME]
        openstack_tenant_name = params[Configuration.ENV.OS_TENANT_NAME]
        openstack_password = params[Configuration.ENV.OS_PASSWORD]
        openstack_auth_url = params[Configuration.ENV.OS_AUTH_URL]
        openstack_no_cache = params[Configuration.ENV.OS_NO_CACHE]
        openstack_admin_token = params[Configuration.ENV.OS_ADMIN_TOKEN]
        mysql_user = params[Configuration.ENV.MYSQL_USER]
        mysql_password = params[Configuration.ENV.MYSQL_PASSWORD]
        keystone_user = params[Configuration.ENV.KEYSTONE_USER]
        keystone_password = params[Configuration.ENV.KEYSTONE_PASSWORD]
        control_address = params[Configuration.ENV.CONTROL_ADDRESS]

        self.comment("*** Keystone Install ***")


        # Set up credentials
        self.add("export OS_TENANT_NAME=" + openstack_tenant_name)
        self.add("export OS_USERNAME=" + openstack_user)
        self.add("export OS_PASSWORD=" + openstack_password)
        self.add("export OS_AUTH_URL=" + openstack_auth_url)
        self.add("export OS_NO_CACHE=" + openstack_no_cache)

        self.comment("Step 2.6 Keystone")
        self.aptGet("keystone")

        # Create keystone database user and database instance
        create_command = "CREATE DATABASE keystone;"
        create_keystone_user_local_command  = "CREATE USER '" + keystone_user + "'@'localhost' identified by '" + keystone_password + "';"
        create_keystone_user_control_command  = "CREATE USER '" + keystone_user + "'@'" + control_address + "'  identified by '" + keystone_password + "';"
        grant_local_command = "GRANT ALL ON keystone.* to '" + keystone_user + \
            "'@'localhost' IDENTIFIED by '" + keystone_password + "';"
        grant_control_command = "GRANT ALL ON keystone.* to '" + keystone_user + \
            "'@'" + control_address + "' IDENTIFIED by '" + keystone_password + "';"
        self.writeToFile(create_command, "/tmp/keystone.sql")
        self.appendToFile(create_keystone_user_local_command, "/tmp/keystone.sql")
        self.appendToFile(create_keystone_user_control_command, "/tmp/keystone.sql")
        self.appendToFile(grant_local_command, "/tmp/keystone.sql")
        self.appendToFile(grant_control_command, "/tmp/keystone.sql")
        self.executeSQL("/tmp/keystone.sql", mysql_password)

        # Set the SQL connection in /etc/keystone/conf

        connection_command = "connection = mysql:\/\/" + keystone_user + ":" + keystone_password + "@localhost:3306\/keystone"
        self.sed("s/^connection =.*/"+connection_command+"/", 
                 '/etc/keystone/keystone.conf')
        self.add("service keystone restart")
        self.add("keystone-manage db_sync")

        # Fill up the keystone database using the two scripts from
        # the install git repository
        self.aptGet('git')
        self.add('cd /tmp')
        self.add('git clone https://github.com/mseknibilel/OpenStack-Folsom-Install-guide.git')
        self.add('cd OpenStack-Folsom-Install-guide/Keystone_Scripts/With\ Quantum')
        sed_command="s/^HOST_IP=.*/HOST_IP="+control_address+"/"
        self.sed(sed_command, 'keystone_basic.sh')
        self.sed(sed_command, 'keystone_endpoints_basic.sh')
        sed_command="s/^EXT_HOST_IP=.*/EXT_HOST_IP="+control_address+"/"
        self.sed(sed_command, 'keystone_endpoints_basic.sh')

        self.add("chmod a+x keystone_*.sh")
        # Set some variables that these scripts use
        self.add("export ADMIN_PASSWORD=" + openstack_password)
        self.add("export SERVICE_PASSWORD=" + openstack_password)
        self.add("export SERVICE_TENANT_NAME=" + openstack_tenant_name)

        # Run the scripts
        self.add("./keystone_basic.sh")
        self.add("./keystone_endpoints_basic.sh -T " + openstack_admin_token)


        # Test keystone
        self.aptGet("curl openssl")
        self.add("curl http://" + control_address + "/v2.0/endpoints -H 'x-auth-token: ADMIN'")


    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self, params):
        mysql_password = params[Configuration.ENV.MYSQL_PASSWORD]

        self.comment("*** Keystone Uninstall ***")
        self.aptGet("keystone", True)
        drop_command = "DROP DATABASE keystone;"
        self.writeToFile(drop_command, "/tmp/keystone.sql")
        self.executeSQL("/tmp/keystone.sql", mysql_password)

