from GenericInstaller import GenericInstaller
from Configuration import Configuration

class Glance(GenericInstaller):

    # Return a list of command strings for installing this component
    def installCommands(self, params):
        self.comment("*** Glance Install ***")
        self.comment("Step 1. Install packages.")
        self.aptGet('glance glance-api python-glanceclient glance-common')

# Note: there is an inconsistency with current versions
# of keystonecllient and glance.
# Need to change file:
#    /usr/lib/python2.7/dist-packages/python_glanceclient-0.5.1.8.cdc06d9.egg-info/requires.txt
#
#CHANGE:
#python-keystoneclient>=0.1.2,<0.2
#TO:
#python-keystoneclient>=0.1.2
        self.sed('s/python-keystoneclient>=0.1.2,<0.2/python-keystoneclient>=0.1.2/', '/usr/lib/python2.7/dist-packages/python_glanceclient-0.5.1.8.cdc06d9.egg-info/requires.txt')


        self.comment("Step 2. Configure Glance")
        glance_user = params[Configuration.ENV.GLANCE_USER]
        glance_password = params[Configuration.ENV.GLANCE_PASSWORD]
        rabbit_password = params[Configuration.ENV.RABBIT_PASSWORD]
        backup_directory = params[Configuration.ENV.BACKUP_DIRECTORY]

        glance_registry_conf_filename = '/etc/glance/glance-registry.conf'
        service_tenant_name = "service"

        connection = "sql_connection = mysql:\/\/" + glance_user + ":" +\
            glance_password + "@localhost:3306\/glance"

        self.backup("/etc/glance", backup_directory, "glance-registry.conf")
        self.sed("s/^sql_connection.*/" + connection + "/", \
                     glance_registry_conf_filename)
        self.sed("s/^admin_user.*/admin_user = " + glance_user + "/", \
                     glance_registry_conf_filename)
        self.sed("s/^admin_password.*/admin_password = " + glance_password + "/", \
                     glance_registry_conf_filename)
        self.sed("s/^admin_tenant_name.*/admin_tenant_name = " + service_tenant_name + "/", \
                     glance_registry_conf_filename)

        glance_api_filename = "/etc/glance/glance-api.conf"
        self.backup("/etc/glance", backup_directory, "glance-api.conf")
        self.sed("s/^notifier_strategy.*/notifier_strategy = rabbit/", \
                     glance_api_filename)
        self.sed("s/^rabbit_password.*/rabbit_password = " + \
                     rabbit_password + "/", \
                     glance_api_filename)
        connection = "sql_connection = mysql://" + glance_user + ":" +\
            glance_password + "@localhost:3306/glance"
        self.appendToFile(connection, glance_api_filename)
        
        self.add("service glance-api restart && service glance-registry restart")

        self.add("glance-manage db_sync")

        self.comment("Load default images")
        default_images = params[Configuration.ENV.GLANCE_IMAGES]
        for image in default_images:
            image_name = image["name"]
            image_url = image["url"]
            image_url_pieces = image_url.split('/')
            tar_file = image_url_pieces[len(image_url_pieces)-1]
            image_file = image["image_file"]
            self.add("wget " + image_url)
            self.add("tar xvfz " + tar_file)
            self.add("glance image-create --name='" + image_name + "' --public --container-format=ovf --disk-format=qcow2 < " + image_file)
        glance_user = params[Configuration.ENV.GLANCE_USER]



    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self, params):
        self.comment("*** Glance Uninstall ***")
        self.aptGet('glance glance-api python-glanceclient glance-common', True)
        backup_directory = params[Configuration.ENV.BACKUP_DIRECTORY]
        self.restore("/etc/glance", backup_directory, "glance-registry.conf")
        self.restore("/etc/glance", backup_directory, "glance-api.conf")
