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

import platform
import subprocess
import time
import netaddr
import logging
import fileinput
import sys
import os

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

def get_quantum_status():
    success = False
    try:
        command = "quantum net-list"
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
    for host in compute_hosts:
        status[host] = compute_host_ping_status(host)

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

def get_quantum_agent_status():
    cmd = "quantum agent-list"
    print "Checking status of Openstack newtworking software modules: \n"
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
    slice_name = "DUMMY"

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
    mgmt_addr = (netaddr.IPNetwork(osi._getConfigParam('/etc/gram/config.json','management_network_cidr'))).broadcast  
    public_addr = osi._getConfigParam('/etc/gram/config.json','public_subnet_start_ip')

    # get a list of the namespaces
    command = 'ip netns list'
    output = osi._execCommand(command)
    output_lines = output.split('\n')
    # check for both public and mgmt address in each namespace
    has_mgmt = 0
    has_public = 0
    for line in output_lines:
        if not line:
            return None
        try:
            command = 'ip netns exec ' + line + ' ifconfig'
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

def check_mgmt_ns():
    mgmt_ns = _getMgmtNamespace()
    conf_mgmt_ns = osi._getConfigParam('/etc/gram/config.json','mgmt_ns')
    mgmt_net_name = osi._getConfigParam('/etc/gram/config.json','management_network_name')
    mgmt_net_cidr =  osi._getConfigParam('/etc/gram/config.json','management_network_cidr')
    mgmt_net_vlan = osi._getConfigParam('/etc/gram/config.json','management_network_vlan')
    public_subnet_start_ip = osi._getConfigParam('/etc/gram/config.json','public_subnet_start_ip')
    public_subnet_end_ip = osi._getConfigParam('/etc/gram/config.json','public_subnet_end_ip')
    public_gateway_ip = osi._getConfigParam('/etc/gram/config.json','public_gateway_ip')
    public_subnet_cidr = osi._getConfigParam('/etc/gram/config.json','public_subnet_cidr')
    quantum_conf = "/etc/quantum/l3_agent.ini"

    if not mgmt_ns:
        print "WARNING: Management namespace NOT found"
        for x in range(0,10):
            print "Restarting Quantum-L3 service to attempt to recover the namespace - attempt " + str(x)
            osi._execCommand('service quantum-l3-agent restart')
            time.sleep(5)
            mgmt_ns = _getMgmtNamespace()
            if mgmt_ns:
                continue
        if not mgmt_ns:
            print "WARNING: Unable to recover management namespace" 
            input_var = raw_input("Do you wish to recreate the management network? [y/N]: ")
            if input_var == 'y':
              input_var = raw_input("Do must delete 'externalRouter' (router),'public' (network) and " + mgmt_net_name + " (network). Using the Horizon interface is recommended. Have you dont this and are ready to proceed? [y/N] ")
              if input_var == 'y':
                #osi._execCommand('quantum net-delete public')
                #osi._execCommand('quantum net-delete GRAM-mgmt-net')
                #osi._execCommand('quantum router-delete externalRouter')
                cmd = "quantum net-create " + mgmt_net_name + " --provider:network_type vlan --provider:physical_network physnet2 --provider:segmentation_id " + mgmt_net_vlan + " --shared"
                osi._execCommand(cmd)
                cmd = "quantum subnet-create " + mgmt_net_name + " " + mgmt_net_cidr
                output = osi._execCommand(cmd)
                MGMT_SUBNET_ID = osi._getValueByPropertyName(output, 'id')
                cmd = "quantum net-create public --router:external=True"
                output = osi._execCommand(cmd)
                PUBLIC_NET_ID = osi._getValueByPropertyName(output, 'id') 
                cmd = "quantum subnet-create --allocation_pool" + \
                 " start=" + public_subnet_start_ip + \
                 ",end=" + public_subnet_end_ip + \
                 " --gateway=" + public_gateway_ip + \
                 " " + str(PUBLIC_NET_ID) + " " + public_subnet_cidr + \
                 " -- --enable_dhcp=False"
                output = osi._execCommand(cmd)
                cmd = "quantum router-create externalRouter"
                output = osi._execCommand(cmd)
                EXTERNAL_ROUTER_ID = osi._getValueByPropertyName(output, 'id')
                cmd = "quantum router-gateway-set externalRouter " +  PUBLIC_NET_ID
                output = osi._execCommand(cmd)
                cmd = "quantum router-interface-add externalRouter " + MGMT_SUBNET_ID
                output = osi._execCommand(cmd)

                regex = "s/^gateway_external_network_id/#/"
                cmd = "sed -i " + "\""+ regex + "\"" + " " + quantum_conf
                #osi._execCommand(cmd)
                os.system(cmd)
                regex = "s/^\# gateway_external_network_id.*/gateway_external_network_id=" + str(PUBLIC_NET_ID) + "/"
                cmd = "sed -i " + "\""+ regex + "\"" + " " + quantum_conf
                #osi._execCommand(cmd)
                os.system(cmd)

                regex = "s/^router_id/#/"
                cmd = "sed -i " + "\""+ regex + "\"" + " " + quantum_conf
                #osi._execCommand(cmd)
                os.system(cmd)

                regex = "s/\# router_id.*/router_id=" + str(EXTERNAL_ROUTER_ID) + "/"
                cmd = "sed -i " + "\""+ regex + "\"" + " " + quantum_conf
                #osi._execCommand(cmd)
                os.system(cmd)

                osi._execCommand("service quantum-l3-agent restart")
                mgmt_ns = _getMgmtNamespace()

    if mgmt_ns:
        if conf_mgmt_ns and conf_mgmt_ns == mgmt_ns:
            print "Found management namespace and it matches config"
        elif conf_mgmt_ns:
            print "WARNING: Found management namespace but it does not match config"
            print "Rewriting config value"
            _setField('mgmt_ns',mgmt_ns)

def check_openstack_services():
    print 'checking OpenStack services...'
    services = ['nova-api','nova-cert','nova-conductor','nova-consoleauth ','nova-novncproxy','nova-scheduler','quantum-dhcp-agent','quantum-metadata-agent','quantum-server','quantum-l3-agent','quantum-plugin-openvswitch-agent','glance-registry','glance-api','keystone']
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

def check_gram_services():
    print 'Checking GRAM services...'
    services = ['gram-am','gram-ctrl','gram-vmoc','gram-mon','gram-ch']
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

    get_quantum_agent_status()

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

    quantum_status = get_quantum_status()
    if quantum_status:
        print "Quantum - pass"
    else:
        print "Quantum - fail"

    host_status = {}
    if nova_status:
        host_status = get_host_status()
        for state in host_status:
            if not host_status[state]:
                print "Host " + state + " is not reachable by ping"
            else:
                print "Host " + state + " is reachable by ping"

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
        

    template = \
    "GRAM Healthcheck %s: KEY %s NOVA %s GLN %s" + \
        " QNTM %s HOST %s AM %s GRAM %s"
    print template % \
        (hostname, keystone_status, nova_status, \
             glance_status, quantum_status, str(host_status), \
             am_status, gram_status)





if __name__ == "__main__":
        logging.basicConfig()
        perform_gram_healthcheck()
        #time.sleep(GRAM_HEALTHCHECK_INTERVAL)


        
    
