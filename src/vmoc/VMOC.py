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

# Top level module for VMOC (VLAN-based Multiplexed Openflow Controller)

# VMOC is three things
#   It is a POX controller to an OF switch
#   It is a server for a command interface to add/delete sub-controllers
#   It is a client to sub-controllers (acting as a switch)

from pox.core import core
import pox.openflow.libopenflow_01 as of
from  VMOCManagementInterface import VMOCManagementInterface 
from VMOCSwitchConnection import VMOCSwitchConnection
import VMOCSwitchControllerMap as scmap
import time
import threading
import pdb

log = core.getLogger() # Use central logging service


class VMOCController(object):
    def __init__(self):
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        log.debug("Connection %s" % (event.connection))
        switch = VMOCSwitchConnection(event.connection)
        scmap.add_switch_connection(switch)


def launch(management_port = 7001, default_controller_url = "https://localhost:9000"):
    log.debug("VMOC.launch");
    core.registerNew(VMOCController)
    # In case we get a string from command line
    management_port = int(management_port) 
    management_interface = VMOCManagementInterface(management_port, default_controller_url)
    management_interface.start()

