#!/usr/bin/python

# Create GRAM DEB package gram_control.deb and gram_compute.deb
# Usage: python create_gram_packages.py version
#
# The created files are put into /tmp (or as specified in --output_directory)
#
# The version is copied to
# config.json (as an entry for 'gram_version')
# 
# You can ask for the current version by 'gram-am.py --version"

import os
import sys
import logging
import optparse
import subprocess

class PackageCreator:

    def __init__(self):
        self.opts = None
        logging.basicConfig(level=logging.INFO)
        self.parse_args()

    def _execCommand(self, cmd_string) :
        logging.info('Issuing command %s' % cmd_string)
        command = cmd_string.split()
        return subprocess.check_output(command) 

    def parse_args(self) :
        parser = optparse.OptionParser()
        parser.add_option("--version", \
                              help="Version number for gram deb release", \
                              default=None, dest="version")
        parser.add_option("--output_directory", \
                              help="Output directory for deb files", \
                              default="/tmp", dest="output_directory")
        parser.add_option("--gcf_root", \
                              help="Location of local GCF root", \
                              default="/opt/gcf-2.2", dest="gcf_root")
        parser.add_option("--is_update", \
                              help="Use this option to create an update package rather than the full package", \
                              default=False, dest="is_update")
        parser.add_option("--gram_root", \
                              help="Root of the GRAM source tree", \
                              default=os.environ['HOME'], dest="gram_root")
        [self.opts, args] = parser.parse_args()


    # Change the version in the DEBIAN_*/control files
    # Create the two .deb files
    def run(self):

        if self.opts.version is None:
            print "Version must be set"
            sys.exit(0)

        # Check if it's an update packager
        if self.opts.is_update:
            template = "python createupdatedpkg.py --gcf_root=%s --version=%s --gram_root=%s --deb_filename=%s/gram_%s.deb"
            cmd = template % (self.opts.gcf_root,self.opts.version,self.opts.gram_root,self.opts.output_directory, \
                 "update")
            self._execCommand(cmd)
            return

        # Generate the two deb files
        template = "python createdpkg.py --compute_node=%s --gcf_root=%s --deb_filename=%s/gram_%s.deb --version=%s"
        control_command = template % \
            ("False", self.opts.gcf_root, self.opts.output_directory, \
                 "control", self.opts.version)
        compute_command = template % \
            ("True", self.opts.gcf_root, self.opts.output_directory, \
                 "compute",  self.opts.version)
        self._execCommand(control_command)
        self._execCommand(compute_command)
        

if __name__ == "__main__":
    PackageCreator().run()

    

