from GenericInstaller import GenericInstaller
from Configuration import Configuration

class Nova(GenericInstaller):

    nova_directory = "/etc/nova"
    api_paste_filename = "api-paste.ini"
    service_tenant_name = "service"
    config_filename = "nova.conf"

    def __init__(self, controller_node):
        self._controller_node = controller_node

    # Return a list of command strings for installing this component
    def installCommands(self, params):
        self.comment("*** Nova Install ***")
        nova_user = params[Configuration.ENV.NOVA_USER]
        nova_password = params[Configuration.ENV.NOVA_PASSWORD]
        rabbit_password = params[Configuration.ENV.RABBIT_PASSWORD]
        os_password = params[Configuration.ENV.OS_PASSWORD]
        backup_directory = params[Configuration.ENV.BACKUP_DIRECTORY]

        self.aptGet("nova-api nova-cert nova-common nova-scheduler python-nova python-novaclient nova-consoleauth novnc nova-novncproxy")


        self.backup(self.nova_directory, backup_directory, \
                        self.api_paste_filename)
        self.sed("s/admin_tenant_name.*/admin_tenant_name = " + \
                     self.service_tenant_name + "/", 
                 self.nova_directory + "/" + self.api_paste_filename)
        self.sed("s/admin_user.*/admin_user = " + nova_user + "/", 
                 self.nova_directory + "/" + self.api_paste_filename)
        self.sed("s/admin_password.*/admin_password = " + os_password + "/", 
                 self.nova_directory + "/" + self.api_paste_filename)
        self.sed("/volume/d", 
                 self.nova_directory + "/" + self.api_paste_filename)

        self.backup(self.nova_directory, backup_directory, \
                        self.config_filename)
        nova_conf = self.nova_directory + "/" + self.config_filename
        connection = "sql_connection = mysql://" + nova_user + ":" +\
            nova_password + "@localhost:3306/nova"

        self.writeToFile("[DEFAULT]", nova_conf)
        self.appendToFile("# MySQL Connection #", nova_conf)
        self.appendToFile(connection, nova_conf)
        self.appendToFile("# nova-scheduler #", nova_conf)
        self.appendToFile("rabbit_password=" + rabbit_password, nova_conf)
        self.appendToFile("scheduler_driver=nova.scheduler.simple.SimpleScheduler", nova_conf)
        self.appendToFile("# nova-api #", nova_conf)
        self.appendToFile("cc_host=192.168.0.1", nova_conf)
        self.appendToFile("auth_strategy=keystone", nova_conf)
        self.appendToFile("s3_host=192.168.0.1", nova_conf)
        self.appendToFile("ec2_host=192.168.0.1", nova_conf)
        self.appendToFile("nova_url=http://192.168.0.1:8774/v1.1/", nova_conf)
        self.appendToFile("ec2_url=http://192.168.0.1:8773/services/Cloud", nova_conf)
        self.appendToFile("keystone_ec2_url=http://192.168.0.1:5000/v2.0/ec2tokens", nova_conf)
        self.appendToFile("api_paste_config=/etc/nova/api-paste.ini", nova_conf)
        self.appendToFile("allow_admin_api=true", nova_conf)
        self.appendToFile("use_deprecated_auth=false", nova_conf)
        self.appendToFile("ec2_private_dns_show_ip=True", nova_conf)
        self.appendToFile("dmz_cidr=169.254.169.254/32", nova_conf)
        self.appendToFile("ec2_dmz_host=192.168.0.1", nova_conf)
        self.appendToFile("metadata_host=192.168.0.1", nova_conf)
        self.appendToFile("metadata_listen=0.0.0.0", nova_conf)
        self.appendToFile("enabled_apis=ec2,osapi_compute,metadata", nova_conf)
        self.appendToFile("# Networking #", nova_conf)
        self.appendToFile("network_api_class=nova.network.quantumv2.api.API", nova_conf)
        self.appendToFile("quantum_url=http://192.168.0.1:9696", nova_conf)
        self.appendToFile("quantum_auth_strategy=keystone", nova_conf)
        self.appendToFile("quantum_admin_tenant_name=service", nova_conf)
        self.appendToFile("quantum_admin_username=" + os_password, nova_conf)
        self.appendToFile("quantum_admin_password=password", nova_conf)
        self.appendToFile("quantum_admin_auth_url=http://192.168.0.1:35357/v2.0", nova_conf)
        self.appendToFile("libvirt_vif_driver=nova.virt.libvirt.vif.LibvirtHybridOVSBridgeDriver", nova_conf)
        self.appendToFile("linuxnet_interface_driver=nova.network.linux_net.LinuxOVSInterfaceDriver", nova_conf)
        self.appendToFile("firewall_driver=nova.virt.libvirt.firewall.IptablesFirewallDriver", nova_conf)
        self.appendToFile("# Cinder #", nova_conf)
        self.appendToFile("volume_api_class=nova.volume.cinder.API", nova_conf)
        self.appendToFile("# Glance #", nova_conf)
        self.appendToFile("glance_api_servers=192.168.0.1:9292", nova_conf)
        self.appendToFile("image_service=nova.image.glance.GlanceImageService", nova_conf)
        self.appendToFile("# novnc #", nova_conf)
        self.appendToFile("novnc_enable=true", nova_conf)
        self.appendToFile("novncproxy_base_url=http://192.168.0.1:6080/vnc_auto.html", nova_conf)
        self.appendToFile("vncserver_proxyclient_address=127.0.0.1", nova_conf)
        self.appendToFile("vncserver_listen=0.0.0.0", nova_conf)
        self.appendToFile("# Misc #", nova_conf)
        self.appendToFile("logdir=/var/log/nova", nova_conf)
        self.appendToFile("state_path=/var/lib/nova", nova_conf)
        self.appendToFile("lock_path=/var/lock/nova", nova_conf)
        self.appendToFile("root_helper=sudo nova-rootwrap /etc/nova/rootwrap.conf", nova_conf)
        self.appendToFile("verbose=true", nova_conf)

#         From the revised Folsom install guide
#         self.writeToFile("[DEFAULT]", nova_conf)
#         self.appendToFile("logdir=/var/log/nova", nova_conf)
#         self.appendToFile("state_path=/var/lib/nova", nova_conf)
#         self.appendToFile("lock_path=/run/lock/nova", nova_conf)
#         self.appendToFile("verbose=True", nova_conf)
#         self.appendToFile("api_paste_config=/etc/nova/api-paste.ini", nova_conf)
#         self.appendToFile("scheduler_driver=nova.scheduler.simple.SimpleScheduler", nova_conf)
#         self.appendToFile("s3_host=100.10.10.51", nova_conf)
#         self.appendToFile("ec2_host=100.10.10.51", nova_conf)
#         self.appendToFile("ec2_dmz_host=100.10.10.51", nova_conf)
#         self.appendToFile("rabbit_host=100.10.10.51", nova_conf)
#         self.appendToFile("rabbit_password=" + rabbit_password, nova_conf)
#         self.appendToFile("dmz_cidr=169.254.169.254/32", nova_conf)
#         self.appendToFile("metadata_host=100.10.10.51", nova_conf)
#         self.appendToFile("metadata_listen=0.0.0.0", nova_conf)
#         self.appendToFile(connection, nova_conf)
#         self.appendToFile("root_helper=sudo nova-rootwrap /etc/nova/rootwrap.conf", nova_conf)
#         self.appendToFile("", nova_conf)
#         self.appendToFile("# Auth", nova_conf)
#         self.appendToFile("auth_strategy=keystone", nova_conf)
#         self.appendToFile("keystone_ec2_url=http://100.10.10.51:5000/v2.0/ec2tokens", nova_conf)
#         self.appendToFile("# Imaging service", nova_conf)
#         self.appendToFile("glance_api_servers=100.10.10.51:9292", nova_conf)
#         self.appendToFile("image_service=nova.image.glance.GlanceImageService", nova_conf)
#         self.appendToFile("", nova_conf)
#         self.appendToFile("# Vnc configuration", nova_conf)
#         self.appendToFile("vnc_enabled=true", nova_conf)
#         self.appendToFile("novncproxy_base_url=http://192.168.100.51:6080/vnc_auto.html", nova_conf)
#         self.appendToFile("novncproxy_port=6080", nova_conf)
#         self.appendToFile("vncserver_proxyclient_address=192.168.100.51", nova_conf)
#         self.appendToFile("vncserver_listen=0.0.0.0", nova_conf)
#         self.appendToFile("", nova_conf)
#         self.appendToFile("# Network settings", nova_conf)
#         self.appendToFile("network_api_class=nova.network.quantumv2.api.API", nova_conf)
#         self.appendToFile("quantum_url=http://100.10.10.51:9696", nova_conf)
#         self.appendToFile("quantum_auth_strategy=keystone", nova_conf)
#         self.appendToFile("quantum_admin_tenant_name=service", nova_conf)
#         self.appendToFile("quantum_admin_username=quantum", nova_conf)
#         self.appendToFile("quantum_admin_password=service_pass", nova_conf)
#         self.appendToFile("quantum_admin_auth_url=http://100.10.10.51:35357/v2.0", nova_conf)
#         self.appendToFile("libvirt_vif_driver=nova.virt.libvirt.vif.LibvirtHybridOVSBridgeDriver", nova_conf)
#         self.appendToFile("linuxnet_interface_driver=nova.network.linux_net.LinuxOVSInterfaceDriver", nova_conf)
#         self.appendToFile("firewall_driver=nova.virt.libvirt.firewall.IptablesFirewallDriver", nova_conf)
#         self.appendToFile("", nova_conf)
#         self.appendToFile("# Compute #", nova_conf)
#         self.appendToFile("compute_driver=libvirt.LibvirtDriver", nova_conf)
#         self.appendToFile("", nova_conf)
#         self.appendToFile("# Cinder #", nova_conf)
#         self.appendToFile("volume_api_class=nova.volume.cinder.API", nova_conf)
#         self.appendToFile("osapi_volume_listen_port=5900", nova_conf)

        self.add('nova-manage db sync')
        self.add('service nova-api restart')
        self.add('service nova-cert restart')
        self.add('service nova-consoleauth restart')
        self.add('service nova-scheduler restart')
        self.add('service novnc restart')


    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self, params):
        self.comment("*** Nova Uninstall ***")
        backup_directory = params[Configuration.ENV.BACKUP_DIRECTORY]

        self.aptGet("nova-api nova-cert nova-common nova-scheduler python-nova python-novaclient nova-consoleauth novnc nova-novncproxy", True)
        self.restore(self.nova_directory, backup_directory, \
                         self.api_paste_filename)
        self.restore(self.nova_directory, backup_directory, self.config_filename)
