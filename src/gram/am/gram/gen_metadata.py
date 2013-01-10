#----------------------------------------------------------------------
# Copyright (c) 2012 Raytheon BBN Technologies
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


def _generateScriptInstalls(scriptFile, installItem) :
    """ Generate text for a script that handles an _InstallItem object:
        1) Get the file from the source URL
        2) Uncompress and/or untar the file, if applicable
        3) Copy the resulting file/tarball to the destination location
    """
    
    theSourceURL = installItem.sourceURL
    theDestinationDirectory = installItem.destination

    # Perform the wget on the source URL
    scriptFile.write('wget -P /tmp %s \n' % theSourceURL)
    scriptFile.write('if [ $? -eq 0 ] \n')
    scriptFile.write('then \n')
    scriptFile.write('    # Download successful \n')

    downloadedFile = '/tmp/%s' % os.path.basname(theSourceURL)

    # Now make sure destination path does not end with a / (unless it
    #    is the directory /)
    dest = theDestinationDirectory
    if dest.endswith("/") and len(dest) > 1 :
        dest = dest[:-1]

    # Create destination directory (and any necessary parent/ancestor
    #    directories in path) if it does not exist
    if not os.path.isdir(dest) :
        scriptFile.write('    mkdir -p %s \n' % dest)

    # Handle compressed and tar'ed files as necessary
    # ISSUE: Do we use the file extension or the installItem.file_type?
    if (downloadedFile.endswith("tgz") or downloadedFile.endswith("tar.gz")) :
        # Uncompress and untar file, and copy to destination location
        scriptFile.write('    tar -C %s -zxvf %s \n' % (dest, downloadedFile))

    elif (downloadedFile.endswith("tar")) :
        # Untar file and copy to destination location
        scriptFile.write('    tar -C %s -xvf %s \n' % (dest, downloadedFile))

    elif (downloadedFile.endswith("gz")) :
        # Copy file to destimation and unzip
        scriptFile.write('    cp %s %s \n' % (downloadedFile, dest))
        zipFile = dest + '/' + os.path.basename(downloadedFile)
        scriptFile.write('    gunzip %s \n' % zipFile)

    else :
        # Some other file type- simply copy file to destination
        scriptFile.write('    cp %s %s \n' % (downloadedFile, dest))

    # Make file accessible to experimenter
    scriptFile.write('    chmod -R 777 %s \n' % dest)
            
    # Delete the downloaded file
    scriptFile.write('    rm %s \n' % downloadedFile)
            
    scriptFile.write('fi \n\n')


def _generateScriptExecutes(scriptFile, executeItem) :
    """ Generate text for a script that handles an _ExecuteItem object by
        invoking its execution in the generated script
    """
    if executeItem.shell == 'sh' or 'bash' :
        scriptFile.write('%s \n\n' % executeItem.command)
    else :
        config.logger.error("Execute script %s is of an unsupported shell type" % item.command)


def _generateAccount(user) :
    """ Generate a script that creates a new user account and adds SSH authentiation
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
        scriptFilename = '/tmp/' + userName + '.txt'
        try:
            scriptFile = open(scriptFilename, 'w')
        except IOError:
            config.logger.error("Failed to open file that creates metadata: %s" % scriptFilename)
            return ""

        scriptFile.write('#!/bin/sh \n')
#        scriptFile.write('# This textual script is auto-generated\n\n')

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


#def configMetadataSvcs(install_list, execute_list, users)
def configMetadataSvcs(users, scriptFilename = 'userdata.txt') :
    """ Generate a script file to be used within the user_data option of a nova boot call
        Parameters-
            install_list: list of _InstallItem class objects to incorporate into the script
            execute_list: list of _ExecuteItem class objects to incorporate into the script
            users: dictionary of json specs describing new accounts to create at boot
    """

    """
    # Generate support for file installs
    if len(install_list) > 0 :
        scriptFile.write('# Install files from source URL''s\n\n')
        for item in install_list :
            _generateScriptInstalls(scriptFile, item)

    # Generate support for execute invocations
    if len(execute_list) > 0 :
        scriptFile.write('# Execute commands after boot\n\n')
        for item in execute_list :
            _generateScriptExecutes(scriptFile, item)
    """

    # Generate support for creating new user accounts
    # Iterate through the list of users and create a separate script text file for each
    # When all files are generated, then combine them into a single gzipped mime file
    cmd_count = 0
    cmd = 'write-mime-multipart --output=%s ' % scriptFilename
    for user in users :
        scriptName = _generateAccount(user)
        if scriptName != "" :
            cmd = cmd + scriptName + ':text/x-shellscript '
            cmd_count = cmd_count + 1

    if cmd_count > 0 : 
        config.logger.info('Issuing command %s' % cmd)
        command = cmd.split()
        subprocess.check_output(command)

        cmd = 'gzip -f %s ' % scriptFilename
        config.logger.info('Issuing command %s' % cmd)
        command = cmd.split()
        subprocess.check_output(command)


