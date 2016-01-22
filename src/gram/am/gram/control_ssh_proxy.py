#!/usr/bin/env python

#----------------------------------------------------------------------
# Copyright (c) 2013-2016 Raytheon BBN Technologies
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
import signal
from gram_ssh_proxy_daemon import GramSSHProxyDaemon

if __name__ == "__main__":
    daemon = GramSSHProxyDaemon('/tmp/gram-ssh-proxy.pid')
    if len(sys.argv) == 2:
            if sys.argv[1] == 'start':
		signal.signal(signal.SIGUSR1, daemon.receive_add_signal)
		signal.signal(signal.SIGUSR2, daemon.receive_remove_signal)
                daemon.start()
#                print "GRAM SSH proxy started"
                sys.exit(0)
            if sys.argv[1] == 'stop':
                daemon.stop()
                print "GRAM SSH proxy stopped"
                sys.exit(0)
            if sys.argv[1] == 'restart':
                daemon.restart()
                sys.exit(0)

    print "USAGE: %s start|stop|restart" % sys.argv[0]
    sys.exit(2)
