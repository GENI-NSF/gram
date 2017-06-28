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

# To be renamed to pis
def _createAllVMs(vms_to_be_provisioned, users, gram_manager, geni_slice):
    
    #config.logger.info('vms_to_be_provisioned = "%s" len of vms = "%s" users = "%s" gram_manager = "%s" geni_slice = "%s" ' % \
#	(vms_to_be_provisioned, vm_len, users, gram_manager, geni_slice)) 

    # List that will hold one script for each user. Script will establish ssh access	
    scriptList = []

    # Parse manifest rspec to get currently allocated pi name
    mani_rspec = geni_slice._manifest_rspec
    temp = mani_rspec.split('"')
    pi_name = temp[13]

    # retrieve proper ip address based on pi name
    pi_list = config.rpi_metadata
    pidata = pi_list[pi_name]
    public_ipv4 = pidata['public_ipv4']
    #config.logger.info("public_ipv4 = %s" % public_ipv4)
    
    HOST = "pi@%s" % public_ipv4
    #config.logger.info("host = %s" % HOST) 
 
    # Generate one init script and one clean script that will handle all users
    initScript=_generateAccount(users)
    cleanScript=_generateClean(users)

    # config.logger.info('scriptList = "%s" ' % (scriptList))
    # config.logger.info('scriptList2 = "%s" ' % (scriptList2))
    
    
    #HOST = "pi@128.89.91.174"
    
    # Copy over and execute each account generation script
    subprocess.call(['chmod', '+x', initScript])
    subprocess.call(['scp', initScript, '%s:/home/pi/temp/initScript.sh' % HOST])
    ssh = subprocess.Popen(["ssh", "%s" % HOST, "sudo", "./temp/initScript.sh"], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Change the state of the "vm"	
    for vm in vms_to_be_provisioned:
        vm.setAllocationState(constants.provisioned)
	vm.setOperationalState(constants.ready)

    # Copy over and execute the clean-up script
    subprocess.call(['chmod', '+x', cleanScript])
    subprocess.call(['scp', cleanScript, '%s:/home/pi/temp/clean.sh' % HOST])

    return None

def _generateAccount(users) :
    """ Generate a script that creates a new user account with SSH authentication, one script for all users
    """

    userName = ""
    scriptFilename = ""
    publicKeys = []

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

    for user in users:
        # Go through every user and get the user's name and ssh public key(s)
        for key in user.keys() :
            # Found a user, there should only be one of these per key in 'user'
            if key == "urn" :
	        if user[key] == "urn:publicid:IDN+geni:boscontroller:gcf+user+gramuser" :
		    pass
	        else :
		    userName = user[key]
		    userName = userName.split("+")[-1]

            # Found a new public key list, store all the public keys for this user
            elif key == "keys" :
                for value in user[key] :
                    publicKeys.append(value)

	# This part of the script is for each user
        # Only install the user account if there is a user to install
        if userName != "" :

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
            scriptFile.write('echo "%s  ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers \n' % userName)

	    # Reset the publicKeys var for the next user
	    publicKeys = []

    scriptFile.close()

    return scriptFilename

def _generateClean(users) :
    """ Generate a script that removes the user and deletes their home directory and SSH access
    """

    userName = ""
    userNames = []
    scriptFilename = ""

    # Create a list of all usernames except for gramuser
    for user in users :
        for key in user.keys() :
            if key == "urn" :
	        if user[key] == "urn:publicid:IDN+geni:boscontroller:gcf+user+gramuser" :
		    pass
	        else :
		    userName = user[key]
		    userName = userName.split("+")[-1]
		    userNames.append(userName)

    if userNames != [] :
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

        for name in userNames:
       	    # Only install the user account if there is a user to install
	    if name != "" :
        	# Delete user and home directory
        	scriptFile.write('deluser --remove-home %s \n' % name)
        	# Remove users from sudoers list
        	scriptFile.write('sed -i "s/%s  ALL=(ALL) NOPASSWD:ALL//g" /etc/sudoers \n' % name)

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

    # retrieve proper ip address based on pi name
    pi_list = config.rpi_metadata
    pidata = pi_list[pi_name]
    public_ipv4 = pidata['public_ipv4']
    #config.logger.info("public_ipv4 = %s" % public_ipv4)
    
    HOST = "pi@%s" % public_ipv4
    #config.logger.info("HOST = %s" % HOST) 

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
        success = _deleteVM(vm, HOST)
        if success :
            vm.setAllocationState(constants.unallocated)
            vm.setOperationalState(constants.stopping)
        else :
            return_val = False


    return return_val

def _deleteVM(vm_object, HOST) :
    """
        Delete the OpenStack VM that corresponds to this vm_object.
        Delete the network ports associated with the VM

        Returns True of VM was successfully deleted.  False otherwise.
    """
    return_val = True

    # Delete the "VM" by executing the clean script
    ssh = subprocess.Popen(["ssh", "%s" % HOST, "sudo", "./temp/clean.sh"], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = ssh.stdout.readlines()
    if result == []:
        error = ssh.stderr.readlines()
        config.logger.info("Error: %s" % error)
	return_val = False
    else:
        config.logger.info("RESULT IS HERE: %s" % result)

    return return_val

