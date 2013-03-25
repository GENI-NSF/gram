import json
import sys

# Python class to establish the environment variables 
# in which context to run an OpenStack/GRAM installaiton
class Configuration:

      def __init__(self, filename="openstack.conf"):
            self._parseFromJson(filename)
            self._fillInDefaults()

      # Get the parsed parameters
      def getParameters(self): return self._dictionary

      # The config file is in JSON format { "key1" : "value1", ... }
      def _parseFromJson(self, filename):
            data = open(filename).read()
            self._dictionary = json.loads(data)

      # Establish defaults for certain values
      __DEFAULTS = {
            "MANAGEMENT_INTERFACE" : 'eth0',
            "CONTROL_INTERFACE" : 'eth1',
            "DATA_INTERFACE" : 'eth2',
            "KEYSTONE_USER" : 'keystone',
            "GLANCE_USER" : 'glance',
            "NOVA_USER" : 'nova',
            "QUANTUM_USER" : 'quantum',
            }

      # Fill in default values for certain variables that may not
      # be set and for who a default is established in __DEFAULTS above
      def _fillInDefaults(self):
            for key in self.__DEFAULTS.keys():
                  default_value = self.__DEFAULTS[key]
                  if not self._dictionary.has_key(key):
                        self._dictionary[key] = default_value


      # List of all defined environment variables
      class ENV:
            MANAGEMENT_INTERFACE = "MANAGEMENT_INTERFACE"
            MANAGEMENT_ADDRESS = "MANAGEMENT_ADDRESS"
            MANAGEMENT_NETMASK = "MANAGEMENT_NETMASK"

            CONTROL_ADDRESS = "CONTROL_ADDRESS"
            CONTROL_INTERFACE = "CONTROL_INTERFACE"
            CONTROL_NETMASK = "CONTROL_NETMASK"

            DATA_INTERFACE = "DATA_INTERFACE"

            MYSQL_USER = "MYSQL_USER"
            MYSQL_PASSWORD = "MYSQL_PASSWORD"

            RABBIT_PASSWORD = "RABBIT_PASSWORD"

            NOVA_USER = "NOVA_USER"
            NOVA_PASSWORD = "NOVA_PASSWORD"

            GLANCE_USER = "GLANCE_USER"
            GLANCE_PASSWORD = "GLANCE_PASSWORD"

            KEYSTONE_USER = "KEYSTONE_USER"
            KEYSTONE_PASSWORD = "KEYSTONE_PASSWORD"

            QUANTUM_USER = "QUANTUM_USER"
            QUANTUM_PASSWORD = "QUANTUM_PASSWORD"

            OS_TENANT_NAME = "OS_TENANT_NAME"
            OS_USERNAME = "OS_USERNAME"
            OS_PASSWORD = "OS_PASSWORD"
            OS_AUTH_URL = "OS_AUTH_URL"
            OS_NO_CACHE = "OS_NO_CACHE"
            OS_REGION_NAME = "OS_REGION_NAME"

            SERVICE_TOKEN = "SERVICE_TOKEN"
            SERVICE_ENDPOINT = "SERVICE_ENDPOINT"

            CONTROLLER_HOST = "CONTROLLER_HOST"
            COMPUTE_HOSTS = "COMPUTE_HOSTS"

            GLANCE_IMAGES = "GLANCE_IMAGES"

            BACKUP_DIRECTORY = "BACKUP_DIRECTORY"

      # Recognized Shell Types
      BASH_SHELL_TYPE = 'bash'

      # Return list of compute hostnames and control-plane addresses
      def getComputeHosts(self):
            return self._dictionary[self.ENV.COMPUTE_HOSTS]

      # Return a string with all the variables defined as 
      # environment variables
      # If shell_type is 'bash' use export VAR=value
      # Other shell types not supported (yet)
      # 
      def dump(self, shell_type = None):
            preamble = ""
            if (shell_type == None):
                  shell_type = self.BASH_SHELL_TYPE
            if shell_type != self.BASH_SHELL_TYPE:
                  print "Unsupported shell type %s" % (shell_type)
                  sys.exit(0)

            for key in self._dictionary.keys():
                  value = self._dictionary[key]
                  if type(value) not in [str, unicode]: continue
                  declaration = self.dump_key(key, value, shell_type)
                  preamble = preamble + declaration

            return preamble

      def dump_key(self, key, value, shell_type):
            if shell_type != self.BASH_SHELL_TYPE:
                  print "Unsupported shell type %s" % (shell_type)
                  sys.exit(0)

            return "export %s=%s\n" % (key, value)


if __name__ == "__main__":
      config = Configuration()
      preamble = config.dump()

      print preamble
      hosts = config.getComputeHosts()
      print "HOSTS = %s" % (hosts)

            

            
            
