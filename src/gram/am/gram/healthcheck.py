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

import open_stack_interface as osi

GRAM_HEALTHCHECK_INTERVAL = 5

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

def compute_am_status(hostname):
    cmd = "grep port= /home/gram/.gcf/gcf_config"
    ret = subprocess.check_output(cmd, shell=True)
#    print "RET = " + str(ret) + " " + str(type(str(ret)))
    lines = ret.split('\n');
#    print "LINES = " + str(lines) + " " + str(len(lines))
    line = lines[len(lines)-2]
#    print "LINE = " + str(line)
    parts = line.split('=')
    gram_port = int(parts[1])
#    print "GP = " + str(gram_port)
    cmd = "/opt/gcf/src/omni.py -V3 -a https://%s:%d getversion" % (hostname, gram_port)
    ret = subprocess.check_output(cmd, \
                              shell=True, \
                              stderr=subprocess.STDOUT)
#    print "RET = " + str(ret)
    return ret.find('Failed') < 0


def perform_gram_healthcheck():
    platform_info = platform.uname()
    hostname = platform_info[1]

    keystone_status = get_keystone_status()
    nova_status = get_nova_status()
    glance_status = get_glance_status()
    quantum_status = get_quantum_status()

    host_status = {}
    if nova_status:
        host_status = get_host_status()

    am_status = compute_am_status(hostname)
        

    print "GRAM Healthcheck %s: KEY %s NOVA %s GLN %s QNTM %s HOST %s AM %s" %\
        (hostname, keystone_status, nova_status, \
             glance_status, quantum_status, str(host_status), am_status)


if __name__ == "__main__":

    while True:
        perform_gram_healthcheck()
        time.sleep(GRAM_HEALTHCHECK_INTERVAL)


        
    
