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
        parser.add_option("--controller", help="controller name", \
                              default=None, dest="controller")
        parser.add_option("--deb_location", help="DEB directory", \
                              default="/tmp/gram_dpkg", dest="deb_location")
        parser.add_option("--deb_filename", help="DEB filename", \
                              default="/tmp/gram.deb", dest="deb_filename")
        parser.add_option("--should_cleanup", \
                              help="should cleanup before generating", 
                              default="True", dest="should_cleanup")
        parser.add_option("--should_generate", \
                              help="should generate DEB file", 
                              default="True", dest="should_generate")
        parser.add_option("--gram_root", \
                              help="source of GRAM tree", 
                              default=os.environ['HOME'], dest="gram_root")

        [self.opts, args] = parser.parse_args()

        self._should_cleanup = (self.opts.should_cleanup == "True")
        self._should_generate = (self.opts.should_generate == "True")

        if self.opts.controller is None:
            logging.error("USAGE -$ createpkg --controller <your controller name>")
            sys.exit(0)


    def update_file(self, filename, old_str, new_str):
        sed_command  = "s/" + old_str + "/" + new_str + "/"
        self._execCommand("sed -i " + sed_command + " " + filename)

    def cleanup(self):
        self._execCommand("rm -rf " + self.opts.deb_location)
        self._execCommand("rm -rf " + self.opts.deb_filename)

    def generate(self):

        # Create the directory sturcture
        self._execCommand("mkdir -p " + self.opts.deb_location)
        self._execCommand("mkdir -p " + self.opts.deb_location + "/opt")
        self._execCommand("mkdir -p " + self.opts.deb_location + "/etc")
        self._execCommand("mkdir -p " + self.opts.deb_location + "/home/gram")
        self._execCommand("mkdir -p " + self.opts.deb_location + "/DEBIAN")

        # Copy source and data files into their package locations
        self._execCommand("cp -Rf " + self.opts.gram_root + "/gram " + self.opts.deb_location + "/home/gram")
        self._execCommand("cp -Rf /opt/gcf-2.2 " + self.opts.deb_location + "/opt")
        self._execCommand("cp -Rf /opt/pox " + self.opts.deb_location + "/opt")
        self._execCommand("cp -Rf /etc/gram " + self.opts.deb_location + "/etc")
        self._execCommand("cp -Rf " + self.opts.gram_root + "/gram/pkg/gram_dpkg/DEBIAN " + self.opts.deb_location)

        # Update config files with user-defined controller node name
        self.update_file(self.opts.deb_location + "/home/gram/gram/omni_config", \
                             "mycontroller", self.opts.controller)
        self.update_file(self.opts.deb_location + "/home/gram/gram/gcf_config", \
                         "mycontroller", self.opts.controller) 

        # Cleaup up some junk before creating archive
        self._execCommand("rm -rf " + self.opts.deb_location + "/etc/gram/snapshots")
        self._execCommand("rm -rf " + self.opts.deb_location + "/etc/gram/snapshots")
        self._execCommand("rm -rf " + self.opts.deb_location + "/home/gram/gram/pkg/gram_dpkg/tmp")
        self._execCommand("rm -rf " + self.opts.deb_location + "/opt/pox/.git")
        self._execCommand("rm -rf " + self.opts.deb_location + "/home/gram//gram/.git")


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

