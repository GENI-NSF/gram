#!/usr/bin/env python

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
