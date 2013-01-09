# Manages information about all registered controllers

import pdb

# Helper class to hold registration information about a given controller
class ControllerEntry(object):
    def __init__(self, controller_url, macs_by_vlan):
        self._controller_url = controller_url
        self._macs_by_vlan = macs_by_vlan

    def __str__(self):
        image = ""
        for vlan in self._macs_by_vlan.keys():
            image = image + " " + \
                "[" + vlan + ": " + str(self._macs_by_vlan[vlan]) + "] "
        return self._controller_url + ": " + image

    def getURL(self):
        return self__controller_url

    def getMACsByVLAN(self):
        return self._macs_by_vlan

# Hold information about all current controllers and the VLAN/MAC's to which
# they are assigned
class ControllerRegistry(object):

    def __init__(self):
        self._registry = dict();
        self._entries_by_vlan = dict()

    # Don't know why assertions aren't working in this file!

    # Add entries for this controller
    def register(self, controller_url, macs_by_vlan):
        # Check if this entry is redundant with any current entry
        if self._registry.has_key(controller_url):
            raise AssertionError("URL already registered: " + controller_url)
        # Check if VLAN is already registered for some other controller
        for vlan in macs_by_vlan.keys():
            if self._entries_by_vlan.has_key(vlan):
                raise AssertionError("VLAN already defined: " + vlan);

        entry = ControllerEntry(controller_url, macs_by_vlan)
        self._registry[controller_url] = entry;

        # Maintain an index into entries by VLAN tag
        for vlan in macs_by_vlan.keys():
            self._entries_by_vlan[vlan] = entry

    # Remove entries for this controller
    def unregister(self, controller_url):
        # Check if this entry is registered
        if not self._registry.has_key(controller_url):
            raise AssertionError("Undefined URL: " + controller_url)

        entry = self._registry[controller_url]

        for vlan in entry._macs_by_vlan.keys():
            del self._entries_by_vlan[vlan]

        del self._registry[controller_url]

    # Lookup macs by VLAN for given controller
    def lookup_by_url(self, controller_url):
        # Check if this entry is registered
        if not self._registry.has_key(controller_url):
            raise AssertionError("Undefined URL: " + controller_url)
        entry = self._registry[controller_url]
        return entry._controller_client, entry._macs_by_vlan

    # Lookup controller_url and macs_by_vlan for given VLAN tag
    def lookup_by_vlan(self, vlan):
        if not self._entries_by_lan.has_key(vlan):
            raise AssertionError("Undefined VLAN:" + str(vlan))
        entry = self._entries_by_vlan[vlan];
        return entry._controller_url, \
            entry.controller_client, entry._macs_by_vlan

    # Return list of all currently registered controller URL's
    def get_all_urls(self):
        return _registry.keys()

    # Return line-by-line string image of registry
    def dump(self):
        image = ""
        for entry in self._registry.values():
            image = image + str(entry) + "\n"
        return image
