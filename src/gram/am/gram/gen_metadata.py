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

import sys
import stat
import os.path
import uuid
import subprocess
import config
import tempfile

nicInterfaceTempFilePath = '/tmp/tmp_net_inf'
targetVMlocalTempPath = '/tmp/tmpfile'

def _generateScriptInstalls(installItem, scriptFile) :
    """
        Generate text for a script that handles an _InstallItem object:
        1) Get the file from the source URL
        2) Uncompress and/or untar the file, if applicable
        3) Copy the resulting file/tarball to the destination location

        NOTE: In order to preserve the proper user-defined sequence of the install
        and execute requests, we must embed all install items within the same
        cloud-config script. As such, the implementation of this script to perserve
        the sequence is a little unconventional- This function creates the content
        for a cloud-config script that in turn generates a shell script on the target VM,
        which in turn handles the install... three degrees of indirection.
    """
    
    theSourceURL = installItem.source_url
    theDestinationDirectory = installItem.destination

    # Perform the wget on the source URL
    scriptFile.write(' - [ sh, -c, "echo \'#!/bin/sh \' > %s " ]\n' % targetVMlocalTempPath)
    scriptFile.write(' - [ sh, -c, "echo \'wget -P /tmp %s \' >> %s " ]\n' % (theSourceURL, targetVMlocalTempPath))
    scriptFile.write(' - [ sh, -c, "echo \'if [ $? -eq 0 ]; \' >> %s " ]\n' % targetVMlocalTempPath)
    scriptFile.write(' - [ sh, -c, "echo \'then \' >> %s " ]\n' % targetVMlocalTempPath)

    # For HTTP gets, remove anything after the first "?" character
    strendindex = theSourceURL.find("?")
    theSourceURLsubstr = theSourceURL
    if strendindex != -1 :
        theSourceURLsubstr = theSourceURL[:strendindex]
        
    downloadedFile = '/tmp/%s' % os.path.basename(theSourceURLsubstr)

    # Now make sure destination path does not end with a / (unless it
    #    is the directory /)
    dest = theDestinationDirectory
    if dest.endswith("/") and len(dest) > 1 :
        dest = dest[:-1]

    # Create destination directory (and any necessary parent/ancestor
    #    directories in path) if it does not exist
    if not os.path.isdir(dest) :
        scriptFile.write(' - [ sh, -c, "echo \'    mkdir -p %s \' >> %s "]\n' % (dest, targetVMlocalTempPath))

    # Handle compressed and tar'ed files as necessary
    # ISSUE: Do we use the file extension or the installItem.file_type?
    if (downloadedFile.endswith("tgz") or downloadedFile.endswith("tar.gz")) :
        # Uncompress and untar file, and copy to destination location
        scriptFile.write(' - [ sh, -c, "echo \'    tar -C %s -zxf %s \' >> %s "]\n' % (dest, downloadedFile, targetVMlocalTempPath))

    elif (downloadedFile.endswith("tar")) :
        # Untar file and copy to destination location
        scriptFile.write(' - [ sh, -c, "echo \'    tar -C %s -xf %s \' >> %s "]\n' % (dest, downloadedFile, targetVMlocalTempPath))

    elif (downloadedFile.endswith("gz")) :
        # Copy file to destimation and unzip
        scriptFile.write(' - [ sh, -c, "echo \'    cp %s %s \' >> %s "]\n' % (downloadedFile, dest, targetVMlocalTempPath))
        zipFile = dest + '/' + os.path.basename(downloadedFile)
        scriptFile.write(' - [ sh, -c "echo \'    gunzip %s \' >> %s "]\n' % (zipFile, targetVMlocalTempPath))

    else :
        # Some other file type- simply copy file to destination
        scriptFile.write('- [ sh, -c, "echo \'    cp %s %s \' >> %s" ]\n' % (downloadedFile, dest, targetVMlocalTempPath))

    # Make file accessible to experimenter
    scriptFile.write(' - [ sh, -c, "echo \'    chmod -R 777 %s \' >> %s "]\n' % (dest, targetVMlocalTempPath))
            
    # Delete the downloaded file
    scriptFile.write(' - [ sh, -c, "echo \'    rm -f %s \' >> %s "]\n' % (downloadedFile, targetVMlocalTempPath))
    scriptFile.write(' - [ sh, -c, "echo \'fi \' >> %s " ]\n\n' % targetVMlocalTempPath)

    scriptFile.write(' - [ sh, -c, "chmod 777 %s" ]\n' % targetVMlocalTempPath)
    scriptFile.write(' - [ sh, -c, "%s" ]\n' % targetVMlocalTempPath)
    scriptFile.write(' - [ sh, -c, "rm -f %s" ]\n' % targetVMlocalTempPath)

    return True


def _generateScriptExecutes(executeItem, scriptFile) :
    """ Generate text for a script that handles an _ExecuteItem object by
        invoking its execution in the generated cloud-config script

        NOTE: In order to preserve the proper user-defined sequence of the install
        and execute requests, we must embed all execute items within the same
        cloud-config script. As such, this function creates the content
        for a cloud-config script that in turn invokes a shell script on the target VM
        to makes the execute call.
    """

    if executeItem.shell == 'sh' or 'bash' :
        scriptFile.write(' - [ %s, -c, "%s" ]\n' % (executeItem.shell, executeItem.command))
    else :
        config.logger.error("Execute script %s is of an unsupported shell type" % item.command)
        return False

    return True


def _generateScriptExeAndInstalls(install_list, execute_list) :
    """ Generate a cloud-config script that installs the user defined installs and then
        invokes the user-defined executes; The installs and executes must be bundled into
        a single script in order to preserve the order of the calls defined in the rspec;
        If implemented as separate scripts, cloud-init will invoke the installs and executables
        in a non-deterministic order, which is not desireable.
    """

    # Open a temporary file to hold the cloud-config script
    tempscriptfile = tempfile.NamedTemporaryFile(delete=False)
    scriptFilename = '%s' % tempscriptfile.name
    try:
        scriptFile = open(scriptFilename, 'w')
    except IOError:
        config.logger.error("Failed to open file that creates user executable script: %s" % scriptFilename)
        return ""

    scriptFile.write('#cloud-config\n')
    scriptFile.write('runcmd:\n')

    # Generate support for installs
    cmd_count = True
    for item in install_list :
        if _generateScriptInstalls(item, scriptFile) :
            cmd_count = False

    # Generate support for execute invocations
    for item in execute_list :
        if _generateScriptExecutes(item, scriptFile) :
            cmd_count = False

    # Close the generated file
    scriptFile.close()

    # Exit early if no commands are successful
    if cmd_count :
        return ""

    # Return the script filename
    return scriptFilename


def _generateAccount(user) :
    """ Generate a script that creates a new user account with SSH authentiation
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
        scriptFile.write('useradd -c "%s user" -s /bin/bash -m %s \n' % (userName, userName))

        # Create a random default password for user
#        scriptFile.write(' - openssl rand -base64 6 | tee -a ~%s/.password | passwd -stdin %s \n' % (userName, userName))

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

        scriptFile.close()

    return scriptFilename


def _generateDefaultGatewaySupport(control_nic_prefix, scriptFile) :
    """ Generate script content that configures the local default gateway
    """

    # Generate the script content to assign the default gateway
#    scriptFile.write('desiredgw=`ifconfig | grep \"inet addr:\" | grep \"10.10\" | awk \'{print $2}\' | sed -e \'s/addr://g\' | awk -F\'.\' \'{print $1 \".\" $2 \".\" $3 \".1\"}\'`\n')
    scriptFile.write('desiredgw="%s1"\n' % control_nic_prefix)
    scriptFile.write('currentgw=`netstat -rn | grep \"^0.0.0.0\" | awk \'{print $2}\'`\n')

    scriptFile.write('if [ \"$desiredgw\" != \"$currentgw\" ]; then\n')
    scriptFile.write('    route add default gw $desiredgw\n')
    scriptFile.write('    route delete default gw $currentgw\n')
    scriptFile.write('fi\n')


def _generateNicInterfaceScriptFedora(num_nics, indent, scriptFile) :
    """ Generate the network interface configuration content specific to a Fedora image
    """

    # Generate contents of new /etc/sysconfig/network-scripts files
    # Create the requisite number of interfaces based on the total number of NICs accross all VMs
    nic_count = 0
    while nic_count < num_nics :
        eth_name = 'eth%d' % nic_count
        scriptFile.write('%secho \'DEVICE=%s\' > %s \n' % (indent, eth_name, nicInterfaceTempFilePath))
        scriptFile.write('%secho \'BOOTPROTO=dhcp\' >> %s \n' % (indent, nicInterfaceTempFilePath))
        scriptFile.write('%secho \'ONBOOT=yes\' >> %s \n' % (indent, nicInterfaceTempFilePath))

        scriptFile.write('%smv -f %s /etc/sysconfig/network-scripts/ifcfg-%s\n' % (indent, nicInterfaceTempFilePath, eth_name))
        scriptFile.write('%schmod 644 /etc/sysconfig/network-scripts/ifcfg-%s\n' % (indent, eth_name))
        nic_count = nic_count + 1

    # Complete the script with commands to restart the network
    scriptFile.write('%s/etc/init.d/network restart \n' % indent)


def _generateNicInterfaceScriptDefault(num_nics, indent, scriptFile) :
    """ Generate the default network interface configuration content
    """

    # Generate contents of new /etc/network/interfaces file and put it in a temporary file
    scriptFile.write('%secho \'# This file describes the network interfaces available on your system\' > %s \n' % (indent, nicInterfaceTempFilePath))
    scriptFile.write('%secho \'# and how to activate them. For more information, see interfaces(5).\' >> %s \n' % (indent, nicInterfaceTempFilePath))
    scriptFile.write('%secho \'\' >> %s \n' % (indent, nicInterfaceTempFilePath))
    scriptFile.write('%secho \'# The loopback network interface\' >> %s \n' % (indent, nicInterfaceTempFilePath))
    scriptFile.write('%secho \'auto lo\' >> %s \n' % (indent, nicInterfaceTempFilePath))
    scriptFile.write('%secho \'iface lo inet loopback\' >> %s \n' % (indent, nicInterfaceTempFilePath))

    # Create the requisite number of interfaces based on the total number of NICs accross all VMs
    nic_count = 0
    while nic_count < num_nics :
        scriptFile.write('%secho \'\' >> %s \n' % (indent, nicInterfaceTempFilePath))
        scriptFile.write('%secho \'# The primary network interface\' >> %s \n' % (indent, nicInterfaceTempFilePath))
        eth_name = 'eth%d' % nic_count
        scriptFile.write('%secho \'auto %s\' >> %s \n' % (indent, eth_name, nicInterfaceTempFilePath))
        scriptFile.write('%secho \'iface %s inet dhcp\' >> %s \n' % (indent, eth_name, nicInterfaceTempFilePath))
        nic_count = nic_count + 1

    # Complete the script with commands to bring down the current interfaces, install the new config file,
    # and bring the interfaces back up
    scriptFile.write('%sifdown --all \n' % indent)
    scriptFile.write('%smv -f %s /etc/network/interfaces\n' % (indent, nicInterfaceTempFilePath))
    scriptFile.write('%schmod 666 /etc/network/interfaces\n' % indent)
    scriptFile.write('%sifup --all \n' % indent)


def _generateNicInterfaceScript(num_nics, control_nic_prefix) :
    """ Generate a script that configure the local network interfaces
    """

    # Open the script file for writing
    tempscriptfile = tempfile.NamedTemporaryFile(delete=False)
    scriptFilename = '%s' % tempscriptfile.name
    try:
        scriptFile = open(scriptFilename, 'w')
    except IOError:
        config.logger.error("Failed to open file that creates the network interface script: %s" % scriptFilename)
        return ""

    # First generate portion of script that determines the version of Linux
    scriptFile.write('#!/bin/sh \n')
    scriptFile.write('if [ -f /etc/issue ]; then\n')
    scriptFile.write('    grep -iq fedora /etc/issue\n')
    scriptFile.write('    if [ $? -eq 0 ]; then \n')

    # If image is Fedora, then use the default config
    _generateNicInterfaceScriptFedora(num_nics, "        ", scriptFile)

    # If image is not Fedora, then use the Fedora specific content
    scriptFile.write('    else\n')
    _generateNicInterfaceScriptDefault(num_nics, "        ", scriptFile)

    # If the /etc/issue file is not present, then use the default content    
    scriptFile.write('    fi\n')
    scriptFile.write('else\n')
    _generateNicInterfaceScriptDefault(num_nics, "    ", scriptFile)

    # Generate support to set default gateway
    scriptFile.write('fi\n')
    _generateDefaultGatewaySupport(control_nic_prefix, scriptFile)

    # Close out the file
    scriptFile.close()

    return scriptFilename


def configMetadataSvcs(users, install_list, execute_list, num_nics, control_nic_prefix, scriptFilename = 'userdata.txt') :
    """ Generate a script file to be used within the user_data option of a nova boot call
        Parameters-
            users: dictionary of json specs describing new accounts to create at boot
            install_list: list of _InstallItem class objects to incorporate into the script
            execute_list: list of _ExecuteItem class objects to incorporate into the script
            num_nics: total number of NICs defined for the overall slice
            control_nic_prefix: the first three octets of the control NIC IP address
            scriptFilename: the pathname for the combined generated script
    """

    # Generate script files for network configuration support, file installs, boot executable
    # invocations, and user accounts.
    # When all files are generated, then combine them into a single gzipped mime file
    cmd_count = 0
    cmd = 'write-mime-multipart --output=%s ' % scriptFilename
    rmcmd = 'rm -f'

    # Generate boothook script to reset network interfaces and default gateway
    scriptName = _generateNicInterfaceScript(num_nics, control_nic_prefix)
    if scriptName != "" :
        cmd += scriptName + ':text/cloud-boothook '
        rmcmd += ' %s' % scriptName 
        cmd_count = cmd_count + 1

    # Generate support for file installs and executes
    if len(install_list) > 0 or len(execute_list) > 0 :
        scriptName = _generateScriptExeAndInstalls(install_list, execute_list)
        if scriptName != "" :
            cmd += scriptName + ':text/cloud-config '
            rmcmd += ' %s' % scriptName 
            cmd_count = cmd_count + 1

    # Generate support for creating new user accounts
    # Iterate through the list of users and create a separate script text file for each
    for user in users :
        scriptName = _generateAccount(user)
        if scriptName != "" :
            cmd += scriptName + ':text/x-shellscript '
            rmcmd += ' %s' % scriptName 
            cmd_count = cmd_count + 1
  
    # Combine all scripts into a single mime'd and gzip'ed file, if necessary
    if cmd_count > 0 : 
        config.logger.info('Issuing command %s' % cmd)
        command = cmd.split()
        subprocess.check_output(command)

        cmd = 'gzip -f %s ' % scriptFilename
        config.logger.info('Issuing command %s' % cmd)
        command = cmd.split()
        subprocess.check_output(command)

        # Delete the temporary files
        config.logger.info('Issuing command %s' % rmcmd)
        command = rmcmd.split()
        subprocess.check_output(command)

    return cmd_count
