#----------------------------------------------------------------------
# Copyright (c) 2013 Raytheon BBN Technologies
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

from GenericInstaller import GenericInstaller
from gram.am.gram import config

class Keystone(GenericInstaller):

    # Return a list of command strings for installing this component
    def installCommands(self):

        self.comment("*** Keystone Install ***")

        # Set the SQL connection in /etc/keystone/conf

        self.comment("Step 2. Edit /etc/keystone/keystone.conf")
        keystone_user = config.keystone_user
        keystone_password = config.keystone_password
        keystone_conf_filename = '/etc/keystone/keystone.conf'
        os_password = config.os_password
        os_region_name = config.os_region_name
        service_token = config.service_token
        backup_directory = config.backup_directory

        connection_command = "connection = mysql:\/\/" + \
            keystone_user + ":" + keystone_password + \
            "@localhost\/keystone"
        self.backup("/etc/keystone", backup_directory, "keystone.conf")
        self.sed("s/^connection =.*/"+connection_command+"/", 
                 keystone_conf_filename)

        # Restart keystone and create the database tables
        self.comment("Step 3. Restart Keystone and create DB tables")
        self.add("service keystone restart")
        self.add("keystone-manage db_sync")

        # Install data and enpoints
        self.comment("Step 4. Download data script")
        data_script_url = "https://raw.github.com/mseknibilel/OpenStack-Grizzly-Install-Guide/OVS_MultiNode/KeystoneScripts/keystone_basic.sh"
        data_script_filename = 'keystone_basic.sh'
        self.add("rm -f " + data_script_filename)
        self.add("wget " + data_script_url)
        self.sed("s/HOST_IP=.*/HOST_IP=" + config.control_host_addr +  "/",data_script_filename)
        self.sed("s/^ADMIN_PASSWORD.*/ADMIN_PASSWORD=$\{ADMIN_PASSWORD:-" + config.os_password + "\}/",data_script_filename)
        #self.sed("s/SERVICE_PASSWORD.*/SERVICE_PASSWORD=" + keystone_password + "/",data_script_filename)
        #self.sed("s/SERVICE_TOKEN.*/SERVICE_TOKEN=" + service_token + "/",data_script_filename)
        #self.sed("s/SERVICE_TENANT_NAME.*/SERVICE_TENANT_NAME=" + config.os_tenant_name + "/",data_script_filename) 
        self.add("chmod a+x ./" + data_script_filename)
        self.add("./" + data_script_filename)

        self.comment("Step 5. Download data script")
        endpoints_script_url = "https://raw.github.com/mseknibilel/OpenStack-Grizzly-Install-Guide/OVS_MultiNode/KeystoneScripts/keystone_endpoints_basic.sh"
        endpoints_script_filename = "keystone_endpoints_basic.sh"
        self.add("rm -f " + endpoints_script_filename)
        self.add("wget " + endpoints_script_url)
        self.sed("s/^HOST_IP=.*/HOST_IP=localhost/",endpoints_script_filename)
        self.sed("s/^EXT_HOST_IP.*/EXT_HOST_IP=" + config.external_address + "/",endpoints_script_filename)
        self.sed("s/^MYSQL_USER=.*/MYSQL_USER=" + keystone_user + "/",endpoints_script_filename)
        self.sed("s/^MYSQL_PASSWORD=.*/MYSQL_PASSWORD=" + keystone_password + "/",endpoints_script_filename)
        self.add("chmod a+x ./" + endpoints_script_filename)
        self.add("./" + endpoints_script_filename)

        # Create the novarc file
        self.comment("Step 6. Create novarc file")
        novarc_file = "/etc/novarc"
        self.backup("/etc", backup_directory, "novarc")
        self.writeToFile("export OS_TENANT_NAME=admin", novarc_file)

        self.appendToFile("export OS_USERNAME=admin", novarc_file)
        self.appendToFile("export OS_PASSWORD=" + config.os_password , novarc_file)
        self.appendToFile("export OS_AUTH_URL=http://localhost:5000/v2.0/", novarc_file)
        #self.appendToFile("export OS_NO_CACHE=" + str(config.os_no_cache), novarc_file)
        #self.appendToFile("export OS_REGION_NAME=" + config.os_region_name, novarc_file)
        #self.appendToFile("export SERVICE_TOKEN=" + config.service_token, novarc_file)
        #self.appendToFile("export SERVICE_ENDPOINT=" + config.service_endpoint, novarc_file)

        self.add("source " + novarc_file)


    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        mysql_password = config.mysql_password
        backup_directory = config.backup_directory

        self.comment("*** Keystone Uninstall ***")
        self.restore("/etc/keystone", backup_directory, "keystone.conf")
        self.restore("/etc/keystone", backup_directory, "logging.conf")
        self.restore("/etc", backup_directory, "novarc")
