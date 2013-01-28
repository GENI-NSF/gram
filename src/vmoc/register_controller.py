#!/usr/bin/python

import sys

# Usage register_controller.sh slice controller VLANs 

if len(sys.argv) < 3:
    print "Usage: register_controller.py slice controller vlans"
    sys.exit()


slice_id = sys.argv[1]
controller_url = sys.argv[2]
vlans = sys.argv[3]

#print str(slice_id)
#print str(controller_url)
#print str(vlans)

controller_clause = controller_url
if controller_url != 'null': 
    controller_clause = '"' + controller_url  + '"'


command = 'register {"slice_id":' + '"' + slice_id + '", ' + \
    '"controller_url":' + controller_clause + ', ' + \
    '"vlans":' + '' + vlans + '}'

print command


