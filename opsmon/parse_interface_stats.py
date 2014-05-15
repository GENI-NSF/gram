#! /usr/bin/python 

# Program to parse the output from a Dell Force10 switch on the statistics
# of an interface and to pull out the input packets and bytes and
# output packets and bytes
import sys

# Return a dictionary of 'input_packets', 'input_bytes', 
# 'output_packets', 'output_bytes', 'mac_address', 'line_speed'
def parse_interface_stats(lines):

    if isinstance(lines, basestring): lines=lines.split('\r')

    input_packets = 0
    output_packets = 0
    input_bytes = 0
    output_bytes = 0
    mac_address = ''
    line_speed = 0
    parsing_input = False

    for line in lines:
        if line.find('Input Statistics') >= 0: 
            parsing_input = True
        if line.find('Output Statistics') >= 0: 
            parsing_input = False
        if line.find("Current address is") >= 0:
            parts = line.strip().split(' ')
            mac_address = parts[3]
        if line.find("LineSpeed") >= 0:
            parts = line.strip().split(' ')
            line_speed = int(parts[1]) * 1000000
            
        if line.find('packets,') >= 0:
            parts = line.strip().split(' ')
#            print "PARTS = %s" % parts
            num_packets = int(parts[0])
            num_bytes = int(parts[2])
            if parsing_input:
                input_packets = num_packets
                input_bytes = num_bytes
            else:
                output_packets = num_packets
                output_bytes = num_bytes

    output = {
        'input_packets' : input_packets, 
        'input_bytes' : input_bytes,
        'output_packets' : output_packets,
        'output_bytes' : output_bytes,
        'mac_address' : mac_address,
        'line_speed' : line_speed
        }

    return output


if __name__ == "__main__":
    lines = sys.stdin.readlines()
    stats = parse_interface_stats(lines)
    print "STATS = %s" % stats

                        


    
