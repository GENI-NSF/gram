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

# Modification of the method found in openstack_interface
# Used to allow SSH access to the allocated raspberry pis
# And to restore their file systems to a clean state after upon deletion
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
    # Walk through the list of sliver_objects in slivers and create a list:
    # vms_to_be_provisioned
    vms_to_be_provisioned = list()
    for sliver in slivers :
        if isinstance(sliver, resources.VirtualMachine) :
            # sliver is a vm object
            vms_to_be_provisioned.append(sliver)
    config.logger.info('Provisioning %s vms' % \
                           (len(vms_to_be_provisioned))) 

    create_return = _createAllPiVMs(vms_to_be_provisioned,
                                  users, gram_manager, geni_slice)
    return create_return

# Method where Pis are "provisioned"
def _createAllPiVMs(vms_to_be_provisioned, users, gram_manager, geni_slice):
    
    pi_list = config.rpi_metadata
    pi_names = []

    # Parse manifest rspec to get currently allocated pi name(s)
    mani_rspec = geni_slice._manifest_rspec
    #config.logger.info("MANIFEST RSPEC = %s" % mani_rspec)
    if mani_rspec != None :
        temp = mani_rspec.split('client_id')
	for segment in temp:
	    section = segment.split('"')
	    x =  section[1]
	    #config.logger.info("SECTION[1] = %s" % x)
	    flag = 0
	    for pi in pi_list:
	        if pi == x:
		    flag = 1
	    if flag == 1:
		pi_names.append(x)

        # Generate one init script that will handle all users
        initScript=_generateAccount(users)

	for pi_name in pi_names:
        
            # retrieve proper ip address based on pi name
            pidata = pi_list[pi_name]
            public_ipv4 = pidata['public_ipv4']
    
            HOST = "pi@%s" % public_ipv4
    
            # Copy over and execute each account generation script
            subprocess.call(['chmod', '+x', initScript])
            subprocess.call(['scp', initScript, '%s:/home/pi/temp/initScript.sh' % HOST])
            ssh = subprocess.Popen(["ssh", "%s" % HOST, "sudo", "./temp/initScript.sh"], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Change the state of the "vm"	
        for vm in vms_to_be_provisioned:
            vm.setAllocationState(constants.provisioned)
            vm.setOperationalState(constants.ready)

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

def deleteSlivers(geni_slice, slivers):
    """
        Delete the specified sliver_objects (slivers).  All slivers belong
        to the same slice (geni_slice)

        Returns True if all slivers were successfully deleted.
        Returns False if one or more slivers did not get deleted.
    """
    return_val = True  # Value returned by this method.  Be optimistic!
    success = True
    
    pi_list = config.rpi_metadata
    pi_names = []

    # Parse manifest rspec to get currently allocated pi name(s)
    mani_rspec = geni_slice._manifest_rspec
    #config.logger.info("MANIFEST RSPEC = %s" % mani_rspec)
    if mani_rspec != None :
	
        temp = mani_rspec.split('client_id')
	for segment in temp:
	    section = segment.split('"')
	    x =  section[1]
	    #config.logger.info("SECTION[1] = %s" % x)
	    flag = 0
	    for pi in pi_list:
	        if pi == x:
		    flag = 1
	    if flag == 1:
		pi_names.append(x)

	for pi_name in pi_names:
        
            # retrieve proper ip address based on pi name
            pidata = pi_list[pi_name]
            public_ipv4 = pidata['public_ipv4']
	    NFS = pidata['NFS'] # note, it is X, not clientX, so use accordingly
	    minicom = pidata['minicom']
            #config.logger.info("public_ipv4 = %s" % public_ipv4)
    
            HOST = "pi@%s" % public_ipv4
            #config.logger.info("HOST = %s" % HOST) 
	    #config.logger.info("NFS = %s" % NFS)
	    #config.logger.info("MINICOM = %s" % minicom)
 
	    success = _deleteVM(NFS, minicom)

        # Walk through the list of sliver_objects and create a list:
        # vms_to_be_deleted
        vms_to_be_deleted = list()
        for sliver in slivers :
            if isinstance(sliver, resources.VirtualMachine) :
                # sliver is a vm object
                vms_to_be_deleted.append(sliver)
        config.logger.info('Deleting %s vms' % \
                           (len(vms_to_be_deleted)))

        # For each VM to be deleted, delete the VM and its associated network ports
        for vm in vms_to_be_deleted  :
            if success :
                vm.setAllocationState(constants.unallocated)
                vm.setOperationalState(constants.stopping)
            else :
                return_val = False

    return return_val

def _deleteVM(NFS, minicom) :
    """
        Delete the OpenStack VM that corresponds to this vm_object.
        Delete the network ports associated with the VM

        Returns True if VM was successfully deleted.  False otherwise.
    """
    return_val = True
    # command to be executed, specifying correct NFS client number and minicom outlet number
    command = './tempgram/provision.sh client%s %s' % (NFS, minicom)
    config.logger.info("COMMAND WAS: %s " % (command))
    # Delete the "VM" by overwriting the file system and power cycling the outlet
    # SSH -t accesses the server laptop using a pseudo terminal to allow for minicom to run
    ssh = subprocess.Popen(["ssh", "-t", "aorta@128.89.72.91", "sudo", command], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = ssh.stdout.readlines()
    if result == []:
        error = ssh.stderr.readlines()
        config.logger.info("Error: %s" % error)
	return_val = False
    else:
        config.logger.info("Successful execution")
        #config.logger.info("RESULT IS HERE: %s" % result)

    return return_val
