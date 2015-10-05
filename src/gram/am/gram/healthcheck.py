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

# Routine to check the health of a gram rack
# 1. Are the essential openstack services up? [keystone, nova, quntum, glance]?
# 2. Are the compute nodes up?
# 3. Is gram up?
# 4. Can we allocate/release a VM with gram?

# Eventually this output should report to NAGIOS or some
# other health-check system. For now it prints a report periodically

import config
import platform
import subprocess
import time
import netaddr
import logging
import fileinput
import sys
import os
import random

import open_stack_interface as osi

GRAM_HEALTHCHECK_INTERVAL = 600 # Every 10 minutes

def get_keystone_status():
    success = False
    try:
        command = "keystone tenant-list"
        tenants = osi._execCommand(command)
        success = True
    except:
        pass
    return success

def get_nova_status():
    success = False
    try:
        hosts = osi._listHosts('compute')
        success = True
    except:
        pass
    return success

def get_glance_status():
    success = False
    try:
        images = osi._listImages()
        success = True
    except:
        pass
    return success

def get_network_status():
    success = False
    net_node_addr = config.network_host_addr
    try:
        command = '%s net-list' % config.network_type
        output = osi._execCommand(command)
        success = True
    except:
        pass
    return success

def compute_host_ping_status(host):
    ret = subprocess.call("ping -c 1 %s" % host, \
                              shell=True, \
                              stdout=open('/dev/null', 'w'), \
                              stderr=subprocess.STDOUT);
#    print "RET(%s) = %s" % (host, ret)
    return ret == 0

def get_host_status():    
    compute_hosts = osi._listHosts('compute').keys()
#    print "HOSTS = " + str(compute_hosts)

    status = {}
    cmd = "nova-manage service list"
    ret = subprocess.check_output(cmd, shell=True)
    lines = ret.split('\n');
    for host in compute_hosts:
        found = 0
        for line in lines:
            if line.find(host):
                if line.find(':-)'):
                    status[host] = ':-)'
                    found = 0
                    continue
                else:
                    status[host] = 'xxx'
            if found == 0:
                status[host] = 'xxx'
          

        #status[host] = compute_host_ping_status(host)

    return  status

def get_compute_status():
    print "Checking the status of the compute hosts: \n"
    cmd = "nova-manage service list"
    ret = subprocess.check_output(cmd, shell=True)
    lines = ret.split('\n');
    print lines[0]
    for line in lines:
        if not line.find('nova-compute') < 0:
            if not line.find('xxx') < 0:
                print 'WARNING: compute host is down or not properly configured: \n'
            print line   
    print "\n"

def get_network_agent_status():
    net_node_addr = config.network_host_addr
    cmd = '%s agent-list' % config.network_type
    print "Checking status of Openstack networking software modules: \n"
    ret = subprocess.check_output(cmd, shell=True)
    lines = ret.split('\n');
    print lines[0]
    for line in lines:
        if not line.find('xxx') < 0:
            print 'WARNING: the followng agent is down or not properly configured (ignore if it is a duplicate entry): \n'
        print line   
    print "\n"

def compute_gram_port():
    cmd = "grep port= /home/gram/.gcf/gcf_config"
    ret = subprocess.check_output(cmd, shell=True)
#    print "RET = " + str(ret) + " " + str(type(str(ret)))
    lines = ret.split('\n');
#    print "LINES = " + str(lines) + " " + str(len(lines))
    line = lines[len(lines)-2]
#    print "LINE = " + str(line)
    parts = line.split('=')
    gram_port = int(parts[1])
    gram_port = 5001
    return gram_port

def compute_am_status(hostname):
    gram_port = compute_gram_port()
#    print "GP = " + str(gram_port)
    cmd = "/opt/gcf/src/omni.py -V3 -a https://%s:%d getversion" % (hostname, gram_port)
    ret = subprocess.check_output(cmd, \
                              shell=True, \
                              stderr=subprocess.STDOUT)
#    print "RET = " + str(ret)
    return ret.find('Failed') < 0

def compute_gram_status(hostname):
    gram_port = compute_gram_port()
    slice_name = "DUMMY" + str(random.randint(1,100000))

    rspec_name = "/tmp/dummy.rspec"
    f = open(rspec_name, 'w')
    f.write('<rspec type="request" xmlns="http://www.geni.net/resources/rspec/3" \
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"  \
        xsi:schemaLocation="http://www.geni.net/resources/rspec/3 \
        http://www.geni.net/resources/rspec/3/request.xsd"><node client_id="foo"/></rspec>\n');
    f.close()

    create_tmpl = "/opt/gcf/src/omni.py -V3 -a https://%s:%d createslice %s %s"
    create_cmd = create_tmpl % (hostname, gram_port, slice_name, rspec_name)
    #print "Creating slice: " + create_cmd
    ret = subprocess.check_output(create_cmd, shell=True, stderr=subprocess.STDOUT)
    
    create_tmpl = "/opt/gcf/src/omni.py -V3 -a https://%s:%d allocate %s %s"
    create_cmd = create_tmpl % (hostname, gram_port, slice_name, rspec_name)
    #print "Allocating:  " + create_cmd
    ret = subprocess.check_output(create_cmd, shell=True, stderr=subprocess.STDOUT)
#    print "RET = " + ret
    create_success = ret.find('Allocated slivers') >= 0
    if create_success:
        print "Allocate - success"
    else:
        print "Allocate - failure"
        print ret

    provision_tmpl = "/opt/gcf/src/omni.py -V3 -a https://%s:%d provision %s"
    provision_cmd = provision_tmpl % (hostname, gram_port, slice_name)
    #print "Provisioning slice: " + create_cmd
    ret = subprocess.check_output(provision_cmd, shell=True, stderr=subprocess.STDOUT)
#    print "RET = " + ret
    provision_success = ret.find('Provisioned slivers') >= 0
    if provision_success:
        print "Provision - success"
    else:
        print "Provision - failure"
        print ret

    delete_tmpl = "/opt/gcf/src/omni.py -V3 -a https://%s:%d delete %s"
    delete_cmd = delete_tmpl % (hostname, gram_port, slice_name)
    #print "Deleting slice: " + delete_cmd
    ret = subprocess.check_output(delete_cmd, shell=True, stderr=subprocess.STDOUT)
#    print "RET = " + ret
    delete_success = ret.find('Result Summary: Deleted') >= 0
    if delete_success:
        print 'Delete - success'
    else:
        print 'Delete - failure'

    return create_success and provision_success and delete_success

def _getMgmtNamespace() :
    """
       Looks at the namespaces on the machine and finds one that has the management
       network and the external network:
    """
    mgmt_addr = (netaddr.IPNetwork(config.management_network_cidr)).broadcast  
    public_addr = config.public_subnet_start_ip
    net_node_addr = config.network_host_addr
    ssh_prefix = 'ssh gram@' + net_node_addr + ' sudo '
    # get a list of the namespaces
    if config.openstack_type == 'grizzly':
        command = 'ip netns list'
    else:
        command = ssh_prefix + 'ip netns list'
        print "Checking for management namespace.\n"

    output = osi._execCommand(command)
    output_lines = output.split('\n')
    # check for both public and mgmt address in each namespace
    has_mgmt = 0
    has_public = 0
    for line in output_lines:
        if not line:
            return None
        try:
            if config.openstack_type == 'grizzly':
                command = 'ip netns exec ' + line + ' ifconfig'
            else:
                command = ssh_prefix + 'ip netns exec ' + line + ' ifconfig'
                print "Checking through ifconfig return.\n"

            ifconfig = osi._execCommand(command)
        except subprocess.CalledProcessError as e:
            continue

        ifconfig_lines = ifconfig.split('\n')
        for ifconfig_line in ifconfig_lines:
            if str(mgmt_addr) in ifconfig_line:
                has_mgmt = 1
            if public_addr in ifconfig_line:
                has_public = 1
        if has_mgmt and has_public:
            return line
        else:
            has_mgmt = 0
            has_public = 0
    return None

def _setField(field,value):
    for line in fileinput.input('/etc/gram/config.json', inplace=1):
        if field in line:
            if field == 'mgmt_ns':
                line = line.replace(line,'   "' + field + '": "' + value + '"\n' )
            else:
                line = line.replace(line,'   "' + field + '": "' + value + '",\n' )
        sys.stdout.write(line)

def check_mgmt_ns(recreate=False):
    mgmt_ns = _getMgmtNamespace()
    conf_mgmt_ns = config.mgmt_ns
    mgmt_net_name = config.management_network_name
    mgmt_net_cidr =  config.management_network_cidr
    mgmt_net_vlan = config.management_network_vlan
    public_subnet_start_ip = config.public_subnet_start_ip
    public_subnet_end_ip = config.public_subnet_end_ip
    public_gateway_ip = config.public_gateway_ip
    public_subnet_cidr = config.public_subnet_cidr
    net_node_addr = config.network_host_addr
    network_conf = "/etc/%s/l3_agent.ini" % config.network_type

    if not mgmt_ns or recreate:
        print "WARNING: Management namespace NOT found"
        if config.network_type == 'quantum':
            nscmd = 'sudo quantum-l3-agent restart' 
        else:
            nscmd = 'ssh gram@' + net_node_addr + \
                ' sudo service neutron-l3-agent restart'
        for x in range(0,10):
            print "Restarting L3 service to attempt to recover the namespace - attempt " + str(x)
            osi._execCommand(nscmd)
            time.sleep(20)
            mgmt_ns = _getMgmtNamespace()
            if mgmt_ns:
                break
        if not mgmt_ns:
            print "WARNING: Unable to recover management namespace" 
            input_var = raw_input("Do you wish to recreate the management network? [y/N]: ")
            if input_var == 'y':
              input_var = raw_input("You must delete 'externalRouter' (router),'public' (network) and " + mgmt_net_name + " (network). Using the Horizon interface is recommended. Have you done this and are ready to proceed? [y/N] ")
              if input_var == 'y':
                  cmd = ("%s net-create " + mgmt_net_name + " --provider:network_type vlan --provider:physical_network physnet2 --provider:segmentation_id " + mgmt_net_vlan + " --shared") % config.network_type
                  osi._execCommand(cmd)
                  cmd = ("%s subnet-create " + mgmt_net_name + " " + mgmt_net_cidr) % config.network_type
                  output = osi._execCommand(cmd)
                  MGMT_SUBNET_ID = osi._getValueByPropertyName(output, 'id')
                  cmd = ("%s net-create public --router:external=True") % config.network_type
                  output = osi._execCommand(cmd)
                  PUBLIC_NET_ID = osi._getValueByPropertyName(output, 'id') 
                  cmd = ("%s subnet-create --allocation_pool" + \
                        " start=" + public_subnet_start_ip + \
                        ",end=" + public_subnet_end_ip + \
                        " --gateway=" + public_gateway_ip + \
                        " " + str(PUBLIC_NET_ID) + " " + public_subnet_cidr + \
                        " -- --enable_dhcp=False") % config.network_type

                  output = osi._execCommand(cmd)
                  cmd = ("%s router-create externalRouter") % config.network_type
                  output = osi._execCommand(cmd)
                  EXTERNAL_ROUTER_ID = osi._getValueByPropertyName(output, 'id')
                  cmd = ("%s router-gateway-set externalRouter " +  PUBLIC_NET_ID) % config.network_type
                  output = osi._execCommand(cmd)
                  cmd = ("%s router-interface-add externalRouter " + MGMT_SUBNET_ID) % config.network_type
                  output = osi._execCommand(cmd)

                  if config.openstack_type == "juno":
                      print "Sending public net id to the network node.\n"
                      cmd = "ssh gram@" + net_node_addr +  " echo " + PUBLIC_NET_ID + " > /home/gram/neutron_public_net"
                      output = osi._execCommand(cmd)

                      print "Sending external router id to the network node.\n"
                      cmd = "ssh gram@" + net_node_addr +  " echo " + EXTERNAL_ROUTER_ID + " > /home/gram/neutron_ext_router"
                      output = osi._execCommand(cmd)
                      
                      print "Rewriting network node neutron l3 agent config files.\n"
                      cmd = "ssh gram@" + net_node_addr + " sudo /home/gram/gram/juno/install/network_files/synch_control_network.sh"
                      osi._execCommand(cmd)

                  else:
                      osi._execCommand("service neutron-l3-agent restart")


                  mgmt_ns = _getMgmtNamespace()

    if mgmt_ns:
        if conf_mgmt_ns and conf_mgmt_ns == mgmt_ns:
            print "Found management namespace and it matches config"
        elif conf_mgmt_ns:
            print "WARNING: Found management namespace but it does not match config"
            print "Rewriting config value"
            _setField('mgmt_ns',mgmt_ns)
            osi._execCommand("service gram-am restart")

def check_openstack_services():
    print 'checking OpenStack services...'
    if config.openstack_type == "juno":
        services = ['nova-api','nova-cert','nova-conductor','nova-consoleauth ','nova-novncproxy','nova-scheduler', 'neutron-server', 'glance-registry','glance-api','keystone']
        remote_services = ['neutron-dhcp-agent','neutron-metadata-agent', 'neutron-l3-agent','neutron-plugin-openvswitch-agent']
    else:
        services = ['nova-api','nova-cert','nova-conductor','nova-consoleauth ','nova-novncproxy','nova-scheduler', 'glance-registry','glance-api','keystone',
                    'quantum-dhcp-agent','quantum-metadata-agent','quantum-server','quantum-l3-agent','quantum-plugin-openvswitch-agent']
        remote_services = []

    for service in services:
        cmd = 'service ' + service + ' status'
        result = osi._execCommand(cmd)
        if not result.find('stop') < 0:
            print 'Warning: the following service is not running, will attempt to restart it - ' + service
            cmd = 'service ' + service + ' restart'
            osi._execCommand(cmd)
            cmd = 'service ' + service + ' status'
            result = osi._execCommand(cmd)
            if result.find('stop'):
                print 'Error: the following service is still not running, check logs in /var/logs'
        else:
            print service + ' - running'

    net_node_addr = osi._getConfigParam('/etc/gram/config.json','network_host_addr')
    for service in remote_services:
        print 'Network node status for ' + service + '\n'
        cmd = 'ssh gram@' + net_node_addr + ' service ' + service + ' status'
        result = osi._execCommand(cmd)
        if not result.find('stop') < 0:
            print 'Warning: the following service is not running, will attempt to restart it - ' + service
            cmd = 'ssh gram@' + net_node_addr + ' service ' + service + ' restart'
            cmd = 'service ' + service + ' restart'
            osi._execCommand(cmd)
            print 'Checking status\n'
            cmd = 'ssh gram@' + net_node_addr + ' service ' + service + ' status'
            result = osi._execCommand(cmd)
            if result.find('stop'):
                print 'Error: the following service is still not running, check logs in /var/logs'
        else:
            print service + ' - running'

def check_gram_services():
    print 'Checking GRAM services...'
    services = ['gram-am','gram-ctrl','gram-vmoc','gram-ch']
    for service in services:
        cmd = 'service ' + service + ' status'
        result = osi._execCommand(cmd)
        if not result.find('stop') < 0:
            print 'Warning: the following service is not running, will attempt to restart it - ' + service
            cmd = 'service ' + service + ' restart'
            osi._execCommand(cmd)
            cmd = 'service ' + service + ' status'
            result = osi._execCommand(cmd)
            if result.find('stop'):
                print 'Error: the following service is still not running - ' + service + '\nCheck logs in /var/logs/upstart/'
        else:
            print service + ' - running'

def perform_gram_healthcheck():
    print "Starting healthcheck"

    check_gram_services()
    check_openstack_services()
    check_mgmt_ns()

    platform_info = platform.uname()
    hostname = platform_info[1]

    get_compute_status()

    get_network_agent_status()

    keystone_status = get_keystone_status()
    if keystone_status:
        print "Keystone - pass"
    else:
        print "Keystone - fail"

    nova_status = get_nova_status()
    if nova_status:
        print "Nova - pass"
    else:
        print "Nova - fail"

    glance_status = get_glance_status()
    if glance_status:
        print "Glance - pass"
    else:
        print "Glance - fail"

    network_status = get_network_status()
    if network_status:
        print "Network - pass"
    else:
        print "Network - fail"

    #host_status = {}
    #if nova_status:
    #    host_status = get_host_status()
    #    for state in host_status:
    #        if not host_status[state]:
    #            print "Host " + state + " is not reachable by ping"
    #        else:
    #            print "Host " + state + " is reachable by ping"

    am_status = compute_am_status(hostname)
    if am_status:
        print "AM is up : Get-Version succeeded at AM"
    else:
        print "AM is down : Get-Version failed at AM"


    gram_status = compute_gram_status(hostname)
    if gram_status:
        print "AM is functioning"


    # TTD
    # Create and delete a sliver
    # Log it to a log file
    # Turn this into a service that logs to a log file
        

    #template = \
    #"GRAM Healthcheck %s: KEY %s NOVA %s GLN %s" + \
    #    " QNTM %s HOST %s AM %s GRAM %s"
    #print template % \
    #    (hostname, keystone_status, nova_status, \
    #         glance_status, neutron_status, str(host_status), \
    #         am_status, gram_status)





if __name__ == "__main__":
    config.initialize('/etc/gram/config.json')
    logging.basicConfig()

    if len(sys.argv) > 1:
        if sys.argv[1] == 'recreate':
            check_mgmt_ns(True) 
    perform_gram_healthcheck()
        #check_mgmt_ns(True)
        #time.sleep(GRAM_HEALTHCHECK_INTERVAL)

        
    
