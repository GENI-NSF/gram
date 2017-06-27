#----------------------------------------------------------------------
# Copyright (c) 2013-2016 Raytheon BBN Technologies
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

import subprocess
import pdb
import re
import time
import tempfile
import os
import uuid
import time
import sys
import string
import netaddr
import json
import threading

import resources
import config
import constants
import utils
import gen_metadata
import manage_ssh_proxy

from xml.dom.minidom import *


def provisionResources(geni_slice, slivers, users, gram_manager) :
    """
        Allocate network and VM resources for this slice.
           geni_slice is the slice_object of the slice being provisioned
           sliver_objects is the list of slivers to be provisioned
           users is a list of dictionaries [keys=>list_of_ssh_keys,
                                            urn=>user_urn]

        Returns None on success
        Returns an error message string on failure.  Failure to provision 
        any sliver results in the entire provision call being rolled back.
    """
    # We provision all the links before we provision the VMs
    # Walk through the list of sliver_objects in slivers and create two list:
    # links_to_be_provisioned and vms_to_be_provisioned
    links_to_be_provisioned = list()
    vms_to_be_provisioned = list()
    for sliver in slivers :
        if isinstance(sliver, resources.VirtualMachine) :
            # sliver is a vm object
            vms_to_be_provisioned.append(sliver)
    config.logger.info('Provisioning %s links and %s vms' % \
                           (len(links_to_be_provisioned), 
                            len(vms_to_be_provisioned))) 


    used_ips = []
    for vm in vms_to_be_provisioned :
        for nic in vm.getNetworkInterfaces() :
            nic.enable()
            if nic.getIPAddress():
               used_ips.append(netaddr.IPAddress(nic.getIPAddress())) 

        for nic in vm.getNetworkInterfaces() :
            if not nic.getIPAddress():
                link = nic.getLink()
                if link == None :
                   # NIC is not connected to a link.  Go to next NIC
                    break

                subnet = link.getSubnet()
                if not subnet:
                    subnet = geni_slice.generateSubnetAddress()
                    while subnet in subnets_used:
                        subnet = geni_slice.generateSubnetAddress()
                    link.setSubnet(subnet)
                subnet_addr = netaddr.IPNetwork(subnet)
                for i in range(1,len(subnet_addr)):
                    if not subnet_addr[i] in used_ips:
                        nic.setIPAddress(str(subnet_addr[i]))
                        nic.setNetmask('255.255.255.0')
                        used_ips.append(subnet_addr[i])
                        break
                
    # For each VM, assign IP addresses to all its interfaces that are
    # connected to a network link
    for vm in vms_to_be_provisioned :
        for nic in vm.getNetworkInterfaces() :
            nic.enable()
 
    create_return = _createAllVMs(vms_to_be_provisioned,
                                  users, gram_manager, geni_slice)
    return create_return

def _createAllVMs(vms_to_be_provisioned, users, gram_manager, geni_slice):
    
    vm_len = len(vms_to_be_provisioned)
    #config.logger.info('vms_to_be_provisioned = "%s" len of vms = "%s" users = "%s" gram_manager = "%s" geni_slice = "%s" ' % \
#	(vms_to_be_provisioned, vm_len, users, gram_manager, geni_slice)) 
	
    scriptList = []
    scriptList2 = []
    users2 = []    
    #users2 = [{'keys':['ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCglU3HMVOuUUroW+RsQ8e2J5yY8JjAXDkglHzDs7c8JMP2SKGlMO6F1ADh4LHZqjj56QZP+VCIxex8UB768tca2Q9h06DxcLjGCOVHhgbi1m6v3+9IimtWQhmRygXD6yxEgRv4IFcaQpl08A3ZGBYQRG4CvnkomPThWlsYZfJwO0F37hN9noCA1DtBml1TEwFQ9I2wHv8o16oilX7iU34BWs6JTOD92BB+aXcB757Ne/ahyG1Kpm+QlRuCIOlZSzk6TdX22YSDI3GSrClIFX7fO9ka7RBgxm2/ITBHi5bDXKi9/N1kvUryiPC+ltRA2nFnk7AXRBzBr3e2XC6LBJsPoEu9JMPv5A/NzN2DRAKeQ72AwkgR3IrUnAjI+K3X013ufk67X5Ik5/wccpnLAdJQi7xDbup4gUKMyvuM/rnJRgLN90jz52T3fZegLgP73f3OfXYIgRoEN2as32+TV8cSIF2btWNOTG3X0CfN5VoH73Bka62Q4OwEeQ5XOYwE26/YvWtF+JU8vQKyRehB/ejUE2/tC7jNwPfDfTRfFjh2k5u1/7O1/pAGqduk0qUsRuoZ+KOzJFHPj8VX6qgi/ZxwDSEC7bqBm9UCJ5A03U8Npj177tQ+GvO/E/mAwAmYb+kZlf+RtmFJ+R9j7yB57XscrHs6/Tdfwxcnwnq2XLhZpQ== jmelloni@umass.edu'], 'urn': 'urn:publicid:IDN+geni:boscontroller:gcf+user+jmelloni2'}]    

    mani_rspec = geni_slice._manifest_rspec
    temp = mani_rspec.split('"')
    pi_name = temp[13]
 
    for user in users:
	if user["urn"] == "urn:publicid:IDN+geni:boscontroller:gcf+user+gramuser":
	    config.logger.info("skipping gramuser")
	else :
	    users2.append(user)
	
    for user in users2:
	scriptName=_generateAccount(user)
	scriptList.append(scriptName)
	scriptName2=_generateClean(user)
	scriptList2.append(scriptName2)

    config.logger.info('scriptList = "%s" ' % (scriptList))
    config.logger.info('scriptList2 = "%s" ' % (scriptList2))
    
    HOST = "pi@128.89.91.174"
    COMMAND = "sudo ./temp.sh"
    script = scriptList[0]
    script2 = scriptList2[0]
    config.logger.info('SCRIPT NAME = %s' % (script))
    subprocess.call(['chmod', '+x', script])
    subprocess.call(['chmod', '+x', script2]) 
    subprocess.call(['scp', script, '%s:/home/pi/temp.sh' % HOST ])
    subprocess.call(['scp', script2, '%s:/home/pi/clean.sh' % HOST ])

    ssh = subprocess.Popen(["ssh", "%s" % HOST, "sudo", "./temp.sh"], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = ssh.stdout.readlines()
    if result == []:
	for vm in vms_to_be_provisioned:
	    vm.setAllocationState(constants.provisioned)
	    vm.setOperationalState(constants.ready)
	error = ssh.stderr.readlines()
	config.logger.info("Error: %s" % error)
    else:
	config.logger.info("RESULT IS HERE: %s" % result)

    return None

def _generateAccount(user) :
    """ Generate a script that creates a new user account with SSH authentication
    """

    userName = ""
    scriptFilename = ""
    publicKeys = []

    # Go through every user and get the user's name and ssh public key
    for key in user.keys() :
        # Found a user, there should only be one of these per key in 'user'
        if key == "urn" :
            userName = user[key]
            userName = userName.split("+")[-1]

        # Found a new public key list, store all the public keys
        elif key == "keys" :
            for value in user[key] :
                publicKeys.append(value)

    # Only install the user account if there is a user to install
    if userName != "" :

        # Open the script file for writing
        tempscriptfile = tempfile.NamedTemporaryFile(delete=False)
        scriptFilename = '%s' % tempscriptfile.name
        try:
            scriptFile = open(scriptFilename, 'w')
        except IOError:
            config.logger.error("Failed to open file that creates metadata: %s" % scriptFilename)
            return ""

        # Use sh script
        scriptFile.write('#!/bin/sh \n')

        # Create account with default shell
        scriptFile.write('useradd -c "%s user" -s /bin/bash -m %s\n' % (userName, userName))

        # Configure SSH authentication for new user
        scriptFile.write('mkdir ~%s/.ssh \n' % userName)
        scriptFile.write('chmod 755 ~%s/.ssh \n' % userName)

        # Write the set of user public keys
        for str in publicKeys :
            newstr = str.replace("\n", "")
            scriptFile.write('echo \'%s\' >> ~%s/.ssh/authorized_keys \n' % (newstr, userName))

        # Make ssh authorized keys available
        # Note that in the chown command below requires the escape character printed before the colon (":")
        #   because non-VASL characters in the cloud-config syntax require a qualifier in order to be properly parsed
        scriptFile.write('chmod 644 ~%s/.ssh/authorized_keys \n' % userName)
        scriptFile.write('chown -R %s\\:%s ~%s/.ssh \n' % (userName, userName, userName))

        # Add users to sudoers list
        scriptFile.write('echo "%s  ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers' % userName)

        scriptFile.close()

    return scriptFilename

def _generateClean(user) :
    """ Generate a script that removes the user and deletes their home directory and SSH access
    """

    userName = ""
    scriptFilename = ""

    # Go through every user and get the user's name and ssh public key
    for key in user.keys() :
        # Found a user, there should only be one of these per key in 'user'
        if key == "urn" :
            userName = user[key]
            userName = userName.split("+")[-1]

    # Only install the user account if there is a user to install
    if userName != "" :

        # Open the script file for writing
        tempscriptfile = tempfile.NamedTemporaryFile(delete=False)
        scriptFilename = '%s' % tempscriptfile.name
        try:
            scriptFile = open(scriptFilename, 'w')
        except IOError:
            config.logger.error("Failed to open file that creates metadata: %s" % scriptFilename)
            return ""

        # Use sh script
        scriptFile.write('#!/bin/sh \n')

        # Delete user and home directory
        scriptFile.write('deluser --remove-home %s \n' % userName)

        # Remove users from sudoers list
        scriptFile.write('sed -i "s/%s  ALL=(ALL) NOPASSWD:ALL//g" /etc/sudoers' % userName)

        scriptFile.close()

    return scriptFilename

def deleteSlivers(geni_slice, slivers):
    """
        Delete the specified sliver_objects (slivers).  All slivers belong
        to the same slice (geni_slice)

        Returns True if all slivers were successfully deleted.
        Returns False if one or more slivers did not get deleted.
    """
    return_val = True  # Value returned by this method.  Be optimistic!

    mani_rspec = geni_slice._manifest_rspec
    temp = mani_rspec.split('"')
    pi_name = temp[13]
   # config.logger.info("<><><><> PI NAME = %s" % pi_name)

    # We delete all the VMs before we delete the links.
    # Walk through the list of sliver_objects and create two list:
    # links_to_be_deleted and vms_to_be_deleted
    links_to_be_deleted = list()
    vms_to_be_deleted = list()
    for sliver in slivers :
        if isinstance(sliver, resources.NetworkLink) :
            # sliver is a link object
            links_to_be_deleted.append(sliver)
        elif isinstance(sliver, resources.VirtualMachine) :
            # sliver is a vm object
            vms_to_be_deleted.append(sliver)
    config.logger.info('Deleting %s links and %s vms' % \
                           (len(links_to_be_deleted),
                            len(vms_to_be_deleted)))

    # For each VM to be deleted, delete the VM and its associated network ports
    for vm in vms_to_be_deleted  :
        success = _deleteVM(vm)
        if success :
            vm.setAllocationState(constants.unallocated)
            vm.setOperationalState(constants.stopping)
        else :
            return_val = False


    return return_val

def _deleteVM(vm_object) :
    """
        Delete the OpenStack VM that corresponds to this vm_object.
        Delete the network ports associated with the VM

        Returns True of VM was successfully deleted.  False otherwise.
    """
    return_val = True

    # Delete the VM
    ssh = subprocess.Popen(["ssh", "pi@128.89.91.174", "sudo", "./clean.sh"], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = ssh.stdout.readlines()
    if result == []:
        error = ssh.stderr.readlines()
        config.logger.info("Error: %s" % error)
	return_val = False
    else:
        config.logger.info("RESULT IS HERE: %s" % result)

    return return_val

