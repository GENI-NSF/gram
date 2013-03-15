import json
import sys

# Python class to establish the environment variables 
# in which context to run an OpenStack/GRAM installaiton
class InstallationConfiguration:

      def __init__(self, filename="openstack.conf"):
            self._parseFromJson(filename)
            self._fillInDefaults()

      # The config file is in JSON format { "key1" : "value1", ... }
      def _parseFromJson(self, filename):
            data = open(filename).read()
            self._dictionary = json.loads(data)

      # Establish defaults for certain values
      __DEFAULTS = {
            "MANAGEMENT_INTERFACE" : 'eth0',
            "CONTROL_INTERFACE" : 'eth1',
            "DATA_INTERFACE" : 'eth2',
            }

      # Fill in default values for certain variables that may not
      # be set and for who a default is established in __DEFAULTS above
      def _fillInDefaults(self):
            for key in InstallationConfiguration.__DEFAULTS.keys():
                  default_value = InstallationConfiguration.__DEFAULTS[key]
                  if not self._dictionary.has_key(key):
                        self._dictionary[key] = default_value


      # List of all defined environment variables
      class ENV:
            MANAGEMENT_INTERFACE_VARIABLE = "MANAGEMENT_INTERFACE"
            MANAGEMENT_ADDRESS_VARIABLE = "MANAGEMENT_ADDRESS"
            MANAGEMENT_NETMASK_VARIABLE = "MANAGEMENT_NETMASK"
            CONTROL_ADDRESS_VARIABLE = "CONTROL_ADDRESS"
            CONTROL_INTERFACE_VARIABLE = "CONTROL_INTERFACE"
            CONTROL_NETMASK_VARIABLE = "CONTROL_NETMASK"
            DATA_INTERFACE_VARIABLE = "DATA_INTERFACE"
            MYSQL_USER_VARIABLE = "MYSQL_USER"
            MYSQL_PASSWORD_VARIABLE = "MYSQL_PASSWORD"
            RABBIT_PASSWORD_VARIABLE = "RABBIT_PASSWORD"
            NOVA_PASSWORD_VARIABLE = "NOVA_PASSWORD"
            GLANCE_PASSWORD_VARIABLE = "GLANCE_PASSWORD"
            KEYSTONE_PASSWORD_VARIABLE = "KEYSTONE_PASSWORD"
            QUANTUM_PASSWORD_VARIABLE = "QUANTUM_PASSWORD"
            OS_TENANT_NAME_VARIABLE = "OS_TENANT_NAME"
            OS_USERNAME_VARIABLE = "OS_USERNAME"
            OS_PASSWORD_VARIABLE = "OS_PASSWORD"
            OS_AUTH_URL_VARIABLE = "OS_AUTH_URL"

      # Recognized Shell Types
      BASH_SHELL_TYPE = 'bash'

      # Return a string with all the variables defined as 
      # environment variables
      # If shell_type is 'bash' use export VAR=value
      # Other shell types not supported (yet)
      # 
      def dump(self, shell_type = None):
            preamble = ""
            if (shell_type == None):
                  shell_type = InstallationConfiguration.BASH_SHELL_TYPE
            if shell_type != InstallationConfiguration.BASH_SHELL_TYPE:
                  print "Unsupported shell type %s" % (shell_type)
                  sys.exit(0)

            for key in self._dictionary.keys():
                  value = self._dictionary[key]
                  declaration = self.dump_key(key, value, shell_type)
                  preamble = preamble + declaration

            return preamble

      def dump_key(self, key, value, shell_type):
            if shell_type != InstallationConfiguration.BASH_SHELL_TYPE:
                  print "Unsupported shell type %s" % (shell_type)
                  sys.exit(0)

            return "export %s=%s\n" % (key, value)


if __name__ == "__main__":
      ic = InstallationConfiguration()
      preamble = ic.dump()
      print preamble

            

            
            
