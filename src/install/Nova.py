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

class Nova(GenericInstaller):

    nova_directory = "/etc/nova"
    api_paste_filename = "api-paste.ini"
    service_tenant_name = "service"
    config_filename = "nova.conf"
    nova_compute_filename = "nova-compute.conf"

    def __init__(self, control_node):
        self._control_node = control_node
        self.nova_user = None
        self.nova_password = None
        self.quantum_user = None
        self.quantum_password = None
        self.rabbit_password = None
        self.os_password = None
        self.backup_directory = None
        self.connection = None
        self.control_host = None

    # Return a list of command strings for installing this component
    def installCommands(self):
        self.nova_user = config.nova_user
        self.nova_password = config.nova_password
        self.quantum_user = config.quantum_user
        self.quantum_password = config.quantum_password
        self.rabbit_password = config.rabbit_password
        self.os_password = config.os_password
        self.backup_directory = config.backup_directory
        self.control_host = config.control_host

        self.connection = "sql_connection = mysql://" + \
            self.nova_user + ":" + \
            self.nova_password + "@" + self.control_host + "/nova"

        if self._control_node:
            self.connection = "sql_connection = mysql://" + \
                self.nova_user + ":" + \
                self.nova_password + "@localhost:3306/nova"
            self.installCommandsControl()
        else:
            self.installCommandsCompute()

    def installCommandsControl(self):
        self.comment("*** Nova Install (control) ***")

        self.modify_api_paste_file()

        self.backup(self.nova_directory, self.backup_directory, \
                        self.config_filename)
        nova_conf = self.nova_directory + "/" + self.config_filename
        nova_pol = self.nova_directory + "/policy.json"

        self.writeToFile("[DEFAULT]",nova_conf)
        self.appendToFile("logdir=/var/log/nova",nova_conf)
        self.appendToFile("state_path=/var/lib/nova",nova_conf)
        self.appendToFile("lock_path=/run/lock/nova",nova_conf)
        self.appendToFile("verbose=True",nova_conf)
        self.appendToFile("api_paste_config=/etc/nova/api-paste.ini",nova_conf)
        
        self.appendToFile("scheduler_driver=nova.scheduler.filter_scheduler.FilterScheduler",nova_conf)
        self.appendToFile("rabbit_host=127.0.0.1",nova_conf)
        self.appendToFile("nova_url=http://localhost:8774/v1.1/",nova_conf)
        self.appendToFile(self.connection,nova_conf)
        self.appendToFile("root_helper=sudo nova-rootwrap /etc/nova/rootwrap.conf",nova_conf)

        self.appendToFile("quota_cores=150",nova_conf)
        self.appendToFile("quota_instances=15",nova_conf)

        self.appendToFile("# Auth",nova_conf)
        self.appendToFile("use_deprecated_auth=false",nova_conf)
        self.appendToFile("auth_strategy=keystone",nova_conf)

        self.appendToFile("# Imaging service",nova_conf)
        self.appendToFile("glance_api_servers=localhost:9292",nova_conf)
        self.appendToFile("image_service=nova.image.glance.GlanceImageService",nova_conf)
      
        self.appendToFile("# Vnc configuration",nova_conf)
        self.appendToFile("novnc_enable=true",nova_conf)
        self.appendToFile("novncproxy_base_url=http://localhost:6080/vnc_auto.html",nova_conf)
        self.appendToFile("novncproxy_port=6080",nova_conf)
        self.appendToFile("vncserver_proxyclient_address=127.0.0.1",nova_conf)
        self.appendToFile("vncserver_listen=0.0.0.0",nova_conf) 

        self.appendToFile("# Networking #",nova_conf)
        self.appendToFile("network_api_class=nova.network.quantumv2.api.API",nova_conf)
        self.appendToFile("quantum_url=http://localhost:9696",nova_conf)
        self.appendToFile("quantum_auth_strategy=keystone",nova_conf)
        self.appendToFile("quantum_admin_tenant_name=service",nova_conf)
        self.appendToFile("quantum_admin_username=" + self.quantum_user,nova_conf)
        self.appendToFile("quantum_admin_password=service_pass",nova_conf)
        self.appendToFile("quantum_admin_auth_url=http://localhost:35357/v2.0",nova_conf)
        self.appendToFile("libvirt_vif_driver=nova.virt.libvirt.vif.LibvirtHybridOVSBridgeDriver",nova_conf)
        self.appendToFile("linuxnet_interface_driver=nova.network.linux_net.LinuxOVSInterfaceDriver",nova_conf)
        self.appendToFile("firewall_driver=nova.virt.libvirt.firewall.IptablesFirewallDriver",nova_conf)

        self.appendToFile("service_quantum_metadata_proxy = True",nova_conf)
        self.appendToFile("quantum_metadata_proxy_shared_secret = helloOpenStack",nova_conf)
        self.appendToFile("compute_driver=libvirt.LibvirtDriver",nova_conf)
        
        self.appendToFile("# Cinder #",nova_conf)
        self.appendToFile("volume_api_class=nova.volume.cinder.API",nova_conf)
        self.appendToFile("osapi_volume_listen_port=5900",nova_conf)

        self.add('nova-manage db sync')
        self.add('service nova-api restart')
        self.add('service nova-cert restart')
        self.add('service nova-consoleauth restart')
        self.add('service nova-scheduler restart')

        self.sed('s/.*compute:create:forced_host.*/"compute:create:forced_host": ""/',nova_pol)

    def installCommandsCompute(self):
        self.comment("*** Nova Install (compute) ***")


        self.comment("Configure NOVA")
        self.backup(self.nova_directory, self.backup_directory, self.config_filename)
        nova_conf = self.nova_directory + "/" + self.config_filename

        self.writeToFile("[DEFAULT]",nova_conf)
        self.appendToFile("logdir=/var/log/nova",nova_conf)
        self.appendToFile("state_path=/var/lib/nova",nova_conf)
        self.appendToFile("lock_path=/run/lock/nova",nova_conf)
        self.appendToFile("verbose=True",nova_conf)
        self.appendToFile("api_paste_config=/etc/nova/api-paste.ini",nova_conf)

        self.appendToFile("compute_scheduler_driver=nova.scheduler.simple.SimpleScheduler",nova_conf)
        self.appendToFile("rabbit_host=" + self.control_host ,nova_conf)
        self.appendToFile("nova_url=http://" +  self.control_host + ":8774/v1.1/",nova_conf)
        self.appendToFile(self.connection,nova_conf)
        self.appendToFile("root_helper=sudo nova-rootwrap /etc/nova/rootwrap.conf",nova_conf)

        self.appendToFile("# Auth",nova_conf)
        self.appendToFile("use_deprecated_auth=false",nova_conf)
        self.appendToFile("auth_strategy=keystone",nova_conf)

        self.appendToFile("# Imaging service",nova_conf)
        self.appendToFile("glance_api_servers=" + self.control_host + ":9292",nova_conf)
        self.appendToFile("image_service=nova.image.glance.GlanceImageService",nova_conf)

        self.appendToFile("# Vnc configuration",nova_conf)
        self.appendToFile("novnc_enable=true",nova_conf)
        self.appendToFile("novncproxy_base_url=http://" + self.control_host + ":6080/vnc_auto.html",nova_conf)
        self.appendToFile("novncproxy_port=6080",nova_conf)
        self.appendToFile("vncserver_proxyclient_address=" + self.control_host,nova_conf)
        self.appendToFile("vncserver_listen=0.0.0.0",nova_conf)

        self.appendToFile("# Networking #",nova_conf)
        self.appendToFile("network_api_class=nova.network.quantumv2.api.API",nova_conf)
        self.appendToFile("quantum_url=http://" + self.control_host + ":9696",nova_conf)
        self.appendToFile("quantum_auth_strategy=keystone",nova_conf)
        self.appendToFile("quantum_admin_tenant_name=service",nova_conf)
        self.appendToFile("quantum_admin_username=" + self.quantum_user,nova_conf)
        self.appendToFile("quantum_admin_password=service_pass",nova_conf)
        self.appendToFile("quantum_admin_auth_url=http://" + self.control_host + ":35357/v2.0",nova_conf)
        self.appendToFile("libvirt_vif_driver=nova.virt.libvirt.vif.LibvirtHybridOVSBridgeDriver",nova_conf)
        self.appendToFile("linuxnet_interface_driver=nova.network.linux_net.LinuxOVSInterfaceDriver",nova_conf)
        self.appendToFile("firewall_driver=nova.virt.libvirt.firewall.IptablesFirewallDriver",nova_conf)

        self.appendToFile("service_quantum_metadata_proxy = True",nova_conf)
        self.appendToFile("quantum_metadata_proxy_shared_secret = helloOpenStack",nova_conf)
        self.appendToFile("compute_driver=libvirt.LibvirtDriver",nova_conf)

        self.appendToFile("# Cinder #",nova_conf)
        self.appendToFile("volume_api_class=nova.volume.cinder.API",nova_conf)
        self.appendToFile("osapi_volume_listen_port=5900",nova_conf)

        self.modify_api_paste_file()

        self.backup(self.nova_directory, self.backup_directory, \
                        self.nova_compute_filename)
        nova_compute_file = self.nova_directory + "/" + self.nova_compute_filename
        self.sed("s/libvirt_type.*/libvirt_type=kvm/", nova_compute_file)
        self.appendToFile("libvirt_ovs_bridge=br-int", nova_compute_file)
        self.appendToFile("libvirt_vif_type=ethernet", nova_compute_file)
        self.appendToFile("libvirt_vif_driver=nova.virt.libvirt.vif.LibvirtHybridOVSBridgeDriver", nova_compute_file)
        self.appendToFile("libvirt_use_virtio_for_bridges=True", nova_compute_file)
        
        self.comment("Restart Nova Services")
        self.add("service nova-api-metadata restart")
        self.add("service nova-compute restart")

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        self.nova_user = config.nova_user
        self.nova_password = config.nova_password
        self.rabbit_password = config.rabbit_password
        self.os_password = config.os_password
        self.backup_directory = config.backup_directory
        if self._control_node:
            self.uninstallCommandsControl()
        else:
            self.uninstallCommandsCompute()

    def uninstallCommandsControl(self):
        self.comment("*** Nova Uninstall (control) ***")

        self.restore(self.nova_directory, self.backup_directory, \
                         self.api_paste_filename)
        self.restore(self.nova_directory, self.backup_directory, self.config_filename)

    def uninstallCommandsCompute(self):
        self.comment("*** Nova Uninstall (compute) ***")

        self.restore(self.nova_directory, self.backup_directory, \
                         self.api_paste_filename)
        self.restore(self.nova_directory, self.backup_directory, \
                         self.nova_compute_filename)
        self.restore(self.nova_directory, self.backup_directory, self.config_filename)


    def modify_api_paste_file(self):
        self.backup(self.nova_directory, self.backup_directory, \
                        self.api_paste_filename)

        #self.sed("s/^\[filter:authtoken\].*/\[filter:authtoken\]\nauth_host =" control_host + "\nauth_port = 35357\nauth_protocol = http\nadmin_tenant_name = service\nadmin_user = quantum\nadmin_password = service_pass\n" + "/", \
         #            self.nova_directory + "/" + \
         #            self.api_paste_filename)


        self.sed("s/^auth_host.*/auth_host = " + self.control_host + "/",self.nova_directory + "/" +self.api_paste_filename)
        self.sed("s/^auth_port.*/auth_port = 35357/",self.nova_directory + "/" +self.api_paste_filename)
        self.sed("s/^admin_tenant_name.*/admin_tenant_name = service/",self.nova_directory + "/" +self.api_paste_filename)
        self.sed("s/^admin_user.*/admin_user = nova/",self.nova_directory + "/" +self.api_paste_filename)
        self.sed("s/^admin_password.*/admin_password = service_pass/",self.nova_directory + "/" +self.api_paste_filename)
        self.sed("s/^#signing_dir.*/signing_dirname = \/tmp\/keystone-signing-nova/",self.nova_directory + "/" +self.api_paste_filename)
#        self.sed("s/admin_tenant_name.*/admin_tenant_name = " + \
#                     self.service_tenant_name + "/", 
#                 self.nova_directory + "/" + self.api_paste_filename)
#        self.sed("s/admin_user.*/admin_user = " + self.nova_user + "/", 
#                 self.nova_directory + "/" + self.api_paste_filename)
#        self.sed("s/admin_password.*/admin_password = " + self.os_password + "/", 
#                 self.nova_directory + "/" + self.api_paste_filename)
#        if self._control_node:
#            self.sed("/volume/d", 
#                     self.nova_directory + "/" + self.api_paste_filename)



