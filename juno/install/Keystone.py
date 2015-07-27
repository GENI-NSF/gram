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
        self.add("rm -f /var/lib/keystone/keystone.db")

        # Set the SQL connection in /etc/keystone/conf
        self.comment("Step 2. Edit /etc/keystone/keystone.conf")
        keystone_user = config.keystone_user
        keystone_password = config.keystone_password
        keystone_conf_filename = '/etc/keystone/keystone.conf'
        saved_keystone_conf_filename = '/home/gram/gram/juno/install/control_files/keystone.conf'
        os_password = config.os_password
        os_region_name = config.os_region_name
        service_token = config.service_token
        backup_directory = config.backup_directory

        connection_command = "connection = mysql:\/\/" + \
            keystone_user + ":" + keystone_password + \
            "@" + config.control_host + "\/keystone"
        self.backup("/etc/keystone", backup_directory, "keystone.conf")
        self.add("TMPTOKEN=`openssl rand -hex 10`")
        self.add("cp " + saved_keystone_conf_filename + " " + keystone_conf_filename)
        self.sed("s/^connection =.*/"+connection_command+"/", 
                 keystone_conf_filename)
        self.sed("s/^admin_token=.*/admin_token=${TMPTOKEN}/", keystone_conf_filename)

        # Restart keystone and create the database tables
        self.comment("Step 3. Restart Keystone and create DB tables")
        self.add("su -s /bin/sh -c \"keystone-manage db_sync\" keystone")
        self.add("service keystone restart")
        self.add("sleep 5")
        #Start a cron job that purges expired tokens hourly
        cron_cmd = "(crontab -l -u keystone 2>&1 | grep -q token_flush) || " + \
           "echo '@hourly /usr/bin/keystone-manage token_flush >/var/log/keystone/keystone-tokenflush.log 2>&1' >> /var/spool/cron/crontabs/keystone"
        self.add(cron_cmd)

        # Install data and enpoints
        self.comment("Step 4. Download data script")
        saved_data_script_filename = '/home/gram/gram/juno/install/control_files/keystone_basic.sh'
        data_script_filename = 'keystone_basic.sh'
        self.add("rm -f " + data_script_filename)
        self.add("cp " + saved_data_script_filename + " " + data_script_filename)
        self.sed("s/CONTROL_HOST=.*/CONTROL_HOST=" + config.control_host +  "/",data_script_filename)
        self.sed("s/OS_SERVICE_TOKEN=.*/OS_SERVICE_TOKEN=${TMPTOKEN}/", data_script_filename)
        self.sed("s/OS_PASSWORD=.*/OS_PASSWORD=" + config.os_password + "/",data_script_filename)
        self.sed("s/OS_EMAIL=.*/OS_EMAIL=" + config.control_email_addr + "/",data_script_filename)
        self.sed("s/OS_SERVICE_PASSWORD=.*/OS_SERVICE_PASSWORD=" + config.service_password + "/",data_script_filename)
        self.add("chmod a+x ./" + data_script_filename)
        self.add("./" + data_script_filename)

        # Create the novarc file
        self.comment("Step 5. Create novarc file")
        novarc_file = "/etc/novarc"
        self.backup("/etc", backup_directory, "novarc")
        self.writeToFile("export OS_TENANT_NAME=admin", novarc_file)

        self.appendToFile("export OS_USERNAME=admin", novarc_file)
        self.appendToFile("export OS_PASSWORD=" + config.os_password , novarc_file)
        self.appendToFile("export OS_AUTH_URL=http://" + config.control_host + ":35357/v2.0", novarc_file)
        #self.appendToFile("export OS_NO_CACHE=" + str(config.os_no_cache), novarc_file)
        #self.appendToFile("export OS_REGION_NAME=" + config.os_region_name, novarc_file)
        #self.appendToFile("export SERVICE_TOKEN=" + config.service_token, novarc_file)
        #self.appendToFile("export SERVICE_ENDPOINT=" + config.service_endpoint, novarc_file)
        self.add("sleep 5")
        self.add("source " + novarc_file)


    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        mysql_password = config.mysql_password
        backup_directory = config.backup_directory

        self.comment("*** Keystone Uninstall ***")
        self.restore("/etc/keystone", backup_directory, "keystone.conf")
        self.restore("/etc/keystone", backup_directory, "logging.conf")
        self.restore("/etc", backup_directory, "novarc")
