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

class Glance(GenericInstaller):

    glance_directory = "/etc/glance"
    glance_registry_conf_filename = 'glance-registry.conf'
    glance_api_conf_filename = 'glance-api.conf'
    service_tenant_name = "service"
    saved_glance_registry_conf_filename = "/home/gram/gram/juno/install/control_files/glance-registry.conf"
    saved_glance_api_conf_filename = "/home/gram/gram/juno/install/control_files/glance-api.conf"

    # Return a list of command strings for installing this component
    def installCommands(self):
        self.comment("*** Glance Install ***")
        self.comment("Step 1. Install packages.")

        self.comment("Step 2. Configure Glance")
        glance_user = config.glance_user
        glance_password = config.glance_password
        os_password = config.os_password
        rabbit_password = config.rabbit_password
        backup_directory = config.backup_directory
        control_address = config.control_address

        self.backup(self.glance_directory, backup_directory, \
                        self.glance_registry_conf_filename)
        self.backup(self.glance_directory, backup_directory, \
                        self.glance_api_conf_filename)


        connection_command = "connection = mysql:\/\/" + \
            glance_user + ":" + glance_password + \
            "@" + config.control_host + "\/glance"

        self.comment("Step 3. Configure API conf file")
        self.add("cp " + self.saved_glance_api_conf_filename + " " + \
                 self.glance_directory + "/" + \
                     self.glance_api_conf_filename)

        self.sed("s/^connection =.*/" + connection_command + "/", \
                     self.glance_directory + "/" + \
                     self.glance_api_conf_filename)

        self.sed("s/^auth_uri =.*/auth_uri = http:\/\/" + config.control_host +":5000\/v2.0/", \
                     self.glance_directory + "/" + \
                     self.glance_api_conf_filename)

        self.sed("s/^identity_uri =.*/identity_uri = http:\/\/" + config.control_host +":35357/", \
                     self.glance_directory + "/" + \
                     self.glance_api_conf_filename)

        self.sed("s/^admin_password =.*/admin_password = " + config.service_password + "/", \
                     self.glance_directory + "/" + \
                     self.glance_api_conf_filename)


        self.comment("Step 4. Configure Registry conf file")
        self.add("cp " + self.saved_glance_registry_conf_filename + " " + \
                 self.glance_directory + "/" + \
                     self.glance_registry_conf_filename)


        self.sed("s/^connection =.*/" + connection_command + "/", \
                     self.glance_directory + "/" + \
                     self.glance_registry_conf_filename)

        self.sed("s/^auth_uri =.*/auth_uri = http:\/\/" + config.control_host +":5000\/v2.0/", \
                     self.glance_directory + "/" + \
                     self.glance_registry_conf_filename)

        self.sed("s/^identity_uri =.*/identity_uri = http:\/\/" + config.control_host +":35357/", \
                     self.glance_directory + "/" + \
                     self.glance_registry_conf_filename)

        self.sed("s/^admin_password =.*/admin_password = " + config.service_password + "/", \
                     self.glance_directory + "/" + \
                     self.glance_registry_conf_filename)

        self.add("su -s /bin/sh -c \"glance-manage db_sync\" glance")

        self.add("service glance-registry restart && service glance-api restart")


        self.comment("Load default images")
        default_images = config.glance_images
        for image in default_images:
            image_name = image["name"]
            image_url = image["url"]
            image_url_pieces = image_url.split('/')
            tar_file = image_url_pieces[len(image_url_pieces)-1]
            image_file = image["image_file"]
            self.add("wget " + image_url)
            self.add("tar xvfz " + tar_file)
            self.add("glance image-create --name='" + image_name + "' --public --container-format=ovf --disk-format=qcow2 < " + image_file)
        glance_user = config.glance_user



    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        self.comment("*** Glance Uninstall ***")
        backup_directory = config.backup_directory
        self.restore(self.glance_directory, backup_directory, \
                         self.glance_registry_conf_filename)
        self.restore(self.glance_directory, backup_directory, \
                         self.glance_api_conf_filename)
