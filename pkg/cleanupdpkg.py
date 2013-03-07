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
import subprocess
import logging

def _execCommand(cmd_string) :
    logging.info('Issuing command %s' % cmd_string)
    command = cmd_string.split()
    return subprocess.check_output(command) 


def main(argv=None) :
    logging.basicConfig(level=logging.INFO)
    count = 0

    try: 
        _execCommand("rm -Rf gram_dpkg/tmp/gram")
    except:
        count = count + 1

    try: 
        _execCommand("rm -Rf gram_dpkg/opt/gcf")
    except:
        count = count + 1

    try: 
        _execCommand("rm -Rf gram_dpkg/etc/gram/certs")
    except:
        count = count + 1

    try: 
        _execCommand("rm -Rf gram_dpkg/opt/pox")
    except:
        count = count + 1

    try:
        _execCommand("rm -f *.deb")
    except:
        count = count + 1


if __name__ == "__main__":
    sys.exit(main())
