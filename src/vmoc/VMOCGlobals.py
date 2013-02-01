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




