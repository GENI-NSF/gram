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

# Holds static/global variables for VMOC

import gram.am.gram.config as config

class VMOCGlobals:
    __default_controller_url = None  # URL of default controller (if not provided)

    __vlan_testing = False

    def getDefaultControllerURL():
#    config.logger.info("Getting default controller URL " + str(VMOCGlobals.__default_controller__url))
        if VMOCGlobals.__default_controller_url == None:
            raise RuntimeError('Default Controller URL not set!')
        return VMOCGlobals.__default_controller_url

    def setDefaultControllerURL(default_controller_url):
        VMOCGlobals.__default_controller_url = default_controller_url
#    config.logger.info("Setting default controller URL " + str(VMOCGlobals.__default_controller_url))

    # Are we operating in a network  in which we can test VLAN filtering/matching?
    def getVLANTesting(): return VMOCGlobals.__vlan_testing
    def setVLANTesting(vlan_testing): VMOCGlobals.__vlan_testing = vlan_testing

    getDefaultControllerURL=staticmethod(getDefaultControllerURL)
    setDefaultControllerURL=staticmethod(setDefaultControllerURL)
    getVLANTesting=staticmethod(getVLANTesting)
    setVLANTesting=staticmethod(setVLANTesting)




