from GenericInstaller import GenericInstaller
from gram.am.gram import config

class Glance(GenericInstaller):

    glance_directory = "/etc/glance"
    glance_registry_conf_filename = 'glance-registry.conf'
    glance_registry_ini_filename = 'glance-registry-paste.ini'
    glance_api_conf_filename = 'glance-api.conf'
    glance_api_ini_filename = 'glance-api-paste.ini'
    service_tenant_name = "service"

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
                        self.glance_registry_ini_filename)
        self.backup(self.glance_directory, backup_directory, \
                        self.glance_api_conf_filename)
        self.backup(self.glance_directory, backup_directory, \
                        self.glance_api_ini_filename)


        #self.sed("s/^\[filter:authtoken\].*/\[filter:authtoken\]\nauth_host = localhost\nauth_port = 35357\nauth_protocol = http\nadmin_tenant_name = service\nadmin_user = glance\nadmin_password = service_pass\n" + "/", \
        #             self.glance_directory + "/" + \
        #             self.glance_api_ini_filename)
        self.appendToFile("auth_host = localhost", self.glance_directory + "/" +self.glance_api_ini_filename)
        self.appendToFile("auth_port = 35357",self.glance_directory + "/" +self.glance_api_ini_filename)
        self.appendToFile("auth_protocol = http",self.glance_directory + "/" +self.glance_api_ini_filename)
        self.appendToFile("admin_tenant_name = service",self.glance_directory + "/" +self.glance_api_ini_filename)
        self.appendToFile("admin_user = glance",self.glance_directory + "/" +self.glance_api_ini_filename)
        self.appendToFile("admin_password = service_pass",self.glance_directory + "/" +self.glance_api_ini_filename)    

 
        #self.sed("s/^\[filter:authtoken\].*/\[filter:authtoken\]\nauth_host = localhost\nauth_port = 35357\nauth_protocol = http\nadmin_tenant_name = service\nadmin_user = glance\nadmin_password = service_pass\n" + "/", \
        #             self.glance_directory + "/" + \
        #             self.glance_registry_ini_filename)  

        self.appendToFile("auth_host = localhost",self.glance_directory + "/" +self.glance_registry_ini_filename)
        self.appendToFile("auth_port = 35357",self.glance_directory + "/" +self.glance_registry_ini_filename)
        self.appendToFile("auth_protocol = http",self.glance_directory + "/" +self.glance_registry_ini_filename)
        self.appendToFile("admin_tenant_name = service",self.glance_directory + "/" +self.glance_registry_ini_filename)
        self.appendToFile("admin_user = glance",self.glance_directory + "/" +self.glance_registry_ini_filename)
        self.appendToFile("admin_password = service_pass",self.glance_directory + "/" +self.glance_registry_ini_filename)


        connection = "sql_connection = mysql:\/\/" + glance_user + ":" +\
            glance_password + "@localhost:3306\/glance"

        self.sed("s/^sql_connection.*/" + connection + "/", \
                     self.glance_directory + "/" + \
                     self.glance_registry_conf_filename)

        self.sed("s/^#flavor=.*/flavor= keystone/", \
                     self.glance_directory + "/" + \
                     self.glance_registry_conf_filename)

        self.sed("s/^#flavor=.*/flavor= keystone/", \
                     self.glance_directory + "/" + \
                     self.glance_api_conf_filename)



        self.sed("s/^sql_connection.*/" + connection + "/", \
                     self.glance_directory + "/" + \
                     self.glance_api_conf_filename)
        
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
        backup_directory = config.backup_directory
        self.restore(self.glance_directory, backup_directory, \
                         self.glance_registry_conf_filename)
        self.restore(self.glance_directory, backup_directory, \
                         self.glance_api_conf_filename)
