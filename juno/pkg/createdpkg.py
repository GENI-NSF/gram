#!/usr/bin/python

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

import sys
import os
import subprocess
import optparse
import logging

class CreateDpkg:
    def __init__(self):
        self.opts = None
        self._should_cleanup = True
        self._should_generate = True
        logging.basicConfig(level=logging.INFO)

        # Parse arguments from sys.argv
        self.parse_args()

    def _execCommand(self, cmd_string) :
        logging.info('Issuing command %s' % cmd_string)
        command = cmd_string.split()
        return subprocess.check_output(command) 


    def parse_args(self) :
        parser = optparse.OptionParser()
        parser.add_option("--node", help="control, network or compute", \
                              default="control", dest="node")
        parser.add_option("--deb_location", help="DEB directory", \
                              default="/tmp/gram_dpkg", dest="deb_location")
        parser.add_option("--deb_filename", help="DEB filename", \
                              default="/tmp/gram.deb", dest="deb_filename")
        parser.add_option("--gcf_root", help="GCF installation", \
                              default="/opt/gcf-2.2", dest="gcf_root")
        parser.add_option("--mon_root", help="Monitoring installation", \
                              default="/opt/ops-monitoring", dest="mon_root")
        parser.add_option("--should_cleanup", \
                              help="should cleanup before generating", 
                              default="True", dest="should_cleanup")
        parser.add_option("--should_generate", \
                              help="should generate DEB file", 
                              default="True", dest="should_generate")
        parser.add_option("--gram_root", \
                              help="source of GRAM tree", 
                              default=os.environ['HOME'], dest="gram_root")
        parser.add_option("--version", \
                              help="Version of this GRAM deb release", \
                              default=None, dest="version")

        [self.opts, args] = parser.parse_args()

        if self.opts.version is None:
            print("Version must be set")
            sys.exit(0)

        self._should_cleanup = (self.opts.should_cleanup == "True")
        self._should_generate = (self.opts.should_generate == "True")
        self._node = self.opts.node


    def update_file(self, filename, old_str, new_str):
        sed_command  = "s/" + old_str + "/" + new_str + "/"
        self._execCommand("sed -i " + sed_command + " " + filename)

    def cleanup(self):
        self._execCommand("rm -rf " + self.opts.deb_location)
        self._execCommand("rm -rf " + self.opts.deb_filename)

    def generate(self):

        # Create the directory structure
        self._execCommand("mkdir -p " + self.opts.deb_location)
        self._execCommand("mkdir -p " + self.opts.deb_location + "/opt")
        self._execCommand("mkdir -p " + self.opts.deb_location + "/etc")
        self._execCommand("mkdir -p " + self.opts.deb_location + "/home/gram")
        self._execCommand("mkdir -p " + self.opts.deb_location + "/home/gram/.gcf")

        # Copy source and data files into their package locations
        self._execCommand("cp -Rf " + self.opts.gram_root + "/gram " + \
                              self.opts.deb_location + "/home/gram")
        self._execCommand("cp -Rf " + self.opts.gram_root + "/gram/gcf_config " \
                              + self.opts.deb_location + "/home/gram/.gcf")
        self._execCommand("cp -Rf " + self.opts.gcf_root + " " + \
                              self.opts.deb_location + "/opt")
        self._execCommand("cp -Rf " + self.opts.mon_root + " " + \
                              self.opts.deb_location + "/home/gram")
        self._execCommand("cp -Rf " + self.opts.gram_root + "/gram/etc/gram " \
                              + self.opts.deb_location + "/etc")
        self._execCommand("cp " + self.opts.gram_root + \
                              "/gram/src/gram/am/gram/config.json " + \
                              self.opts.deb_location + "/etc/gram")

        debian_source = "/DEBIAN_control"
        if self._node == "compute": 
            debian_source = "/DEBIAN_compute"
        elif self._node == "network":
            debian_source = "/DEBIAN_network"
                
        self._execCommand("cp -Rf " + \
                              self.opts.gram_root + "/gram/pkg/gram_dpkg/" + \
                              debian_source + " " + self.opts.deb_location)
        self._execCommand("mv " + \
                              self.opts.deb_location + "/" + debian_source + \
                              " " + self.opts.deb_location + "/DEBIAN")

        # Change the version in the DEBIAN control file 
        template = 'sed -i "s/Version.*/Version: ' + \
                      self.opts.version + '/" %s'
#        sed_command = template % (self.opts.deb_location + "/DEBIAN/control")
        sed_command = ['sed', '-i', 's/Version.*/Version: ' + self.opts.version + '/', self.opts.deb_location + "/DEBIAN/control"]
        res  = subprocess.check_output(sed_command)

        #  Install GCF on all nodes
        simple_gcf_root = os.path.basename(self.opts.gcf_root)
        if simple_gcf_root != 'gcf':
             self._execCommand("mv " + self.opts.deb_location + "/opt/" + \
                                simple_gcf_root + " " + \
                                self.opts.deb_location + "/opt/gcf")

        #  Only install POX on control node
        if self._node == "control":
            self._execCommand("git clone -b betta http://github.com/noxrepo/pox")
            self._execCommand("mv pox " + self.opts.deb_location + "/opt")
            #self._execCommand("cp -Rf /opt/pox " + \
            #                      self.opts.deb_location + "/opt")


        # Cleaup up some junk before creating archive
        self._execCommand("rm -rf " + \
                              self.opts.deb_location + "/etc/gram/snapshots")
        self._execCommand("rm -rf " + \
                              self.opts.deb_location + "/etc/gram/snapshots")
        self._execCommand("rm -rf " + \
                              self.opts.deb_location + \
                              "/home/gram/gram/pkg/gram_dpkg/tmp")
        self._execCommand("rm -rf " + \
                              self.opts.deb_location + "/home/gram//gram/.git")
        if self._node == "control":
            self._execCommand("rm -rf " + \
                                  self.opts.deb_location + "/opt/pox/.git")


        # Create the package
        self._execCommand("dpkg-deb -b " + self.opts.deb_location + \
                              " " + self.opts.deb_filename)

    def run(self):
        if self._should_cleanup:
            self.cleanup()
        if self._should_generate:
            self.generate()

if __name__ == "__main__":
    CreateDpkg().run()

