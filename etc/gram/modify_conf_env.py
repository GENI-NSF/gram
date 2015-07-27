#                                                                                              
# modify_conf_env.py file variable config_variable prefix                                                      
#                                                                                              
# Create a 'sed' command to modify the contents of a given config file line                    
# that starts with                                                                             
# prefix variable=old_value into                                                               
# prefix variable=new_value                                                                    
# where new value is taken from the config_variable of the gram.am.gram.config package                                

import sys
from gram.am.gram import config

if __name__ == "__main__":

    if len(sys.argv) !=	5:
	print "Usage: modify_conf_env file variable config_variable prefix"
	sys.exit()
    config.initialize('/etc/gram/config.json')
    filename = sys.argv[1]
    variable = sys.argv[2]
    config_variable = sys.argv[3]
    prefix = sys.argv[4]
    if prefix != "": 
        prefix = prefix + " "
    if config_variable == 'control_host':
        new_value = "http:\/\/" + config.control_host + ":5000\/v2.0\/"  
    else: 
        new_value = getattr(config, config_variable)
    print "sed -i 's/^%s%s=.*/%s%s=%s/' %s" % \
        (prefix, variable, prefix, variable, new_value, filename)
