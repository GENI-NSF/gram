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

class Hypervisor(GenericInstaller):

    libvirt_directory = "/etc/libvirt"
    init_directory = "/etc/init"
    default_directory = "/etc/default"
    qemu_conf_filename = "qemu.conf"
    libvirtd_conf_filename = "libvirtd.conf"
    libvirt_bin_conf_filename = "libvirt-bin.conf"
    libvirt_bin_filename = "libvirt-bin"

    # Return a list of command strings for installing this component
    def installCommands(self):
        backup_directory = config.backup_directory

        self.comment("*** Hypervisor Install ***")

        self.comment("Install packages")

        self.comment("Configure libvirt")
        self.backup(self.libvirt_directory, backup_directory, self.qemu_conf_filename)

        qemu_file = self.libvirt_directory + "/" + self.qemu_conf_filename
        self.appendToFile('cgroup_device_acl = [', qemu_file)
        self.appendToFile('   "/dev/null", "/dev/full", "/dev/zero",', qemu_file)
        self.appendToFile('   "/dev/random", "/dev/urandom",', qemu_file)
        self.appendToFile('   "/dev/ptmx", "/dev/kvm", "/dev/kqemu",', qemu_file)
        self.appendToFile('   "/dev/rtc", "/dev/hpet", "/dev/net/tun",', qemu_file)
        self.appendToFile(']', qemu_file)

        self.comment("Disable KVM default virtual bridge to avoid any confusion")
        self.add("virsh net-destroy default")
        self.add("virsh net-undefine default")

        self.comment("Allow Live Migration")
        self.backup(self.libvirt_directory, backup_directory, self.libvirtd_conf_filename)
        libvirtd_file = self.libvirt_directory + "/" + self.libvirtd_conf_filename
        self.appendToFile("listen_tls = 0", libvirtd_file)
        self.appendToFile("listen_tcp = 1", libvirtd_file)
        self.appendToFile('auth_tcp = "none"', libvirtd_file)

        self.backup(self.init_directory, backup_directory, self.libvirt_bin_conf_filename)
        libvirt_bin_file = self.init_directory + "/" + self.libvirt_bin_conf_filename
        self.sed("s/env libvirtd_opts.*/env libvirtd_opts=\\" + '"' + "-d -l\\" + '"' + "/",
                 self.init_directory + "/" + self.libvirt_bin_conf_filename)

        self.backup(self.default_directory, backup_directory, self.libvirt_bin_filename)
        self.sed("s/libvirtd_opts.*/libvirtd_opts=\\" + '"' + "-d -l\\" + '"' + "/",
                 self.default_directory + "/" + self.libvirt_bin_filename)

        self.add("service libvirt-bin restart")


    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        backup_directory = config.backup_directory

        self.comment("*** Hypervisor Uninstall ***")


        self.restore(self.libvirt_directory, backup_directory, self.qemu_conf_filename)

        self.restore(self.libvirt_directory, backup_directory, self.libvirt_bin_conf_filename)

        self.restore(self.init_directory, backup_directory, self.libvirt_bin_conf_filename)
