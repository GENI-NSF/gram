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
import tempfile

def _execCommand(cmd_string) :
    logging.info('Issuing command %s' % cmd_string)
    command = cmd_string.split()
    return subprocess.check_output(command) 


def parse_args(argv) :
    parser = optparse.OptionParser()
    parser.add_option("--controller", help="controller name", default=None)
    return parser.parse_args()


def update_file(filename, old_str, new_str) :
    tempconfigfile = tempfile.NamedTemporaryFile(delete=False)
    configFilename = '%s' % tempconfigfile.name
    try:
        configFile = open(configFilename, 'w')
    except IOError:
        logging.error("Failed to open temporary config file: %s" % configFilename)
        return True

    try:
        origFile = open(filename, 'r')
    except IOError:
        logging.error("Failed to open file: %s" %  filename)
        return True

    lines = origFile.readlines()
    origFile.close()

    for line in lines :
        newline = line.replace(old_str, new_str)
        configFile.write(newline)

    configFile.close()

    try :
        cmd = 'mv -f %s %s' % (configFilename, filename)
        _execCommand(cmd)
    except :
        return True

    return False


def cleanup_files() :
    count = 0

    # Copy source files to their package locations
    try: 
        if path.exists("gram_dpkg/tmp/gram") :
            _execCommand("rm -Rf gram_dpkg/tmp/gram")
    except:
        count = count + 1

    try: 
        if path.exists("gram_dpkg/opt/gcf") :
            _execCommand("rm -Rf gram_dpkg/opt/gcf")
    except:
        count = count + 1

    try: 
        if path.exists("gram_dpkg/etc/gram/certs") :
            _execCommand("rm -Rf gram_dpkg/etc/gram/certs")
    except:
        count = count + 1

    try: 
        if path.exists("gram_dpkg/opt/pox") :
            _execCommand("rm -Rf gram_dpkg/opt/pox")
    except:
        count = count + 1

    return count


def main(argv=None) :
    if argv is None :
        argv = sys.argv

    opts = parse_args(argv)[0]
    controller_name = opts.controller

    if controller_name is None :
        logging.error("USAGE -$ createpkg --controller <your controller name>")
        return

    logging.basicConfig(level=logging.INFO)

    # First cleanup old stuff if necessary
    cleanup_files()

    # Copy source files to their package locations
    _execCommand("cp -Rf ../../gram /tmp")
    _execCommand("rm -Rf /tmp/gram/pkg")
    _execCommand("mv -f /tmp/gram gram_dpkg/tmp")
    _execCommand("cp -Rf /opt/gcf gram_dpkg/opt")
    _execCommand("cp -Rf /etc/gram/certs gram_dpkg/etc/gram")
    _execCommand("cp -Rf /opt/pox gram_dpkg/opt")

    # Update config files with user-defined controller node name
    if update_file("gram_dpkg/tmp/gram/omni_config", "mycontroller", controller_name) :
        return

    if update_file("gram_dpkg/tmp/gram/gcf_config", "mycontroller", controller_name) :
        return

    # Create the package
    _execCommand("dpkg-deb -b gram_dpkg .")

    # Cleanup copied files
    cleanup_files()


if __name__ == "__main__":
    sys.exit(main())
