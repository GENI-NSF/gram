from GenericInstaller import GenericInstaller
from gram.am.gram import config

class Glance(GenericInstaller):

    glance_directory = "/etc/glance"
    glance_registry_conf_filename = 'glance-registry.conf'
    glance_api_conf_filename = 'glance-api.conf'
    service_tenant_name = "service"

    # Return a list of command strings for installing this component
    def installCommands(self):
        self.comment("*** Glance Install ***")
        self.comment("Step 1. Install packages.")
        self.aptGet('glance glance-api python-glanceclient glance-common')

        self.comment("Step 2. Configure Glance")
        glance_user = config.glance_user
        glance_password = config.glance_password
        os_password = config.os_password
        rabbit_password = config.rabbit_password
        backup_directory = config.backup_directory


        connection = "sql_connection = mysql:\/\/" + glance_user + ":" +\
            glance_password + "@localhost:3306\/glance"

        self.backup(self.glance_directory, backup_directory, \
                        self.glance_registry_conf_filename)
        self.sed("s/^sql_connection.*/" + connection + "/", \
                     self.glance_directory + "/" + \
                     self.glance_registry_conf_filename)
        self.sed("s/^admin_user.*/admin_user = " + glance_user + "/", \
                     self.glance_directory + "/" + \
                     self.glance_registry_conf_filename)
        self.sed("s/^admin_password.*/admin_password = " + os_password + "/", \
                     self.glance_directory + "/" + \
                     self.glance_registry_conf_filename)
        self.sed("s/^admin_tenant_name.*/admin_tenant_name = " + \
                     self.service_tenant_name + "/", \
                     self.glance_directory + "/" + \
                     self.glance_registry_conf_filename)

        self.backup(self.glance_directory, backup_directory, \
                        self.glance_api_conf_filename)
        self.sed("s/^sql_connection.*/" + connection + "/", \
                     self.glance_directory + "/" + \
                     self.glance_api_conf_filename)
        self.sed("s/^admin_user.*/admin_user = " + glance_user + "/", \
                     self.glance_directory + "/" + \
                     self.glance_api_conf_filename)
        self.sed("s/^admin_password.*/admin_password = " + os_password + "/", \
                     self.glance_directory + "/" + \
                     self.glance_api_conf_filename)
        self.sed("s/^admin_tenant_name.*/admin_tenant_name = " + \
                     self.service_tenant_name + "/", \
                     self.glance_directory + "/" + \
                     self.glance_api_conf_filename)

        self.sed("s/^notifier_strategy.*/notifier_strategy = rabbit/", \
                     self.glance_directory + "/" + self.glance_api_conf_filename)
        self.sed("s/^rabbit_password.*/rabbit_password = " + \
                     rabbit_password + "/", \
                     self.glance_directory + "/" + self.glance_api_conf_filename)
        
        self.add("service glance-api restart && service glance-registry restart")

        self.add("glance-manage db_sync")

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
        self.aptGet('glance glance-api python-glanceclient glance-common', True)
        backup_directory = config.backup_directory
        self.restore(self.glance_directory, backup_directory, \
                         self.glance_registry_conf_filename)
        self.restore(self.glance_directory, backup_directory, \
                         self.glance_api_conf_filename)
