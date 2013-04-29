#
# modify_conf_env.py file variable prefix
#
# Create a 'sed' command to modify the contents of a given config file line
# that starts with 
# prefix variable=old_value into
# prefix variable=new_value 
# where new value is taken from the gram.am.gram.config package

import sys
from gram.am.gram import config

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print "Usage: modify_conf_env file variable prefix"
        sys.exit()
    config.initialize('/etc/gram/config.json')
    file = sys.argv[0]
    variable = sys.argv[1]
    prefix = sys.argv[2]
    new_value = dir(config)[variable]
    print "sed -i s/^%s %s=.*/%s %s=%s/ %f" % (prefix, variable, prefix, variable, new_value)

