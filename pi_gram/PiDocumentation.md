# Raspberry Pi on GRAM

### Initialize:

1. SSH into boscontroller
- 1. ssh gram@128.89.91.170
- 2. supply password
2. Activate the GCF clearinghouse
  1. python gcf/src/gcf-ch.py
3. On a different terminal, activate the GENI Aggregate Manager
- 1. ssh into boscontroller (see step 1)
- 2. source admin-openrc (sets environmental variables)
- 3. python gram/src/gram-am.py --config_file ~/gram/src/gram/am/gram/rpi_config.json
- **NOTE**: The above steps 3-2 and 3-3 are currently aliased to "st2" on boscontroller.
- **NOTE**: Step 3-3 activated the Aggregate Manager, but passed in a different config file.
- **NOTE**: rpi_config.json currently has the initial configuration info for the raspberry pis.

### Workflow: 

4. List Resources
- 1. python omni.py -V 3 -a http://128.89.91.170:7010 listresources
- **NOTE**: The above command should return the pi nodes contained within this AM.
- **NOTE**: The property "available" should show you if the resource is currently able to be allocated.
- **NOTE**: If "unavailable" the property "owner" should show you the slice that is using the pi.
5. Create Slice
- 1. python omni.py -V 3 -a http://128.89.91.170:7010 createslice <slicename>
6. Renewslice
- 1. python omni.py -V 3 -a http://128.89.91.170:7010 renewslice <slicename> <YYYYMMDD>
- **NOTE**: Currently, this will return an error, but still properly set the expiration time.
- **NOTE**: Assuming the error is "can't subtract offset-naive and offset-aware datetimes."
- **NOTE**: The above command only renews the slice, not any slivers contained within.
7. Allocate Resources
- 1. python omni.py -V 3 -a http://128.89.91.170:7010 allocate <slicename> <rspec>
- **NOTE**: Rspecs can be found under the /gram/rspecs directory.
- **NOTE**: One exists for any combination of rpi-1 through rpi-5.
- **NOTE**: i.e. ../../gram/rspecs/rpi1_req.rsepc and ../../gram/rspecs/rpi2and4_req.rspec.
- **NOTE**: The "pi-tag" key is what separates the execution thread for pi-specific handling.
- **NOTE**: Make sure the public_ipv4 matches the one found in the listresources step, under the experimental interface.
- **NOTE**: The "VM" that is "made" is currently the way that slivers are handled.
8. Renew sliver
- 1. python omni.py -V 3 -a http://128.89.91.170:7010 renew <slicename> <YYYYMMDD>
- **NOTE**: The above command will renew all slivers in the slice.
9. Provision slice
- 1. python omni.py -V 3 -a http://128.89.91.170:7010 provision <slicename>
- **NOTE**: This will generate an account on the specified pi(s) for each user listed in the omni-config file
- **NOTE**: Boscontroller will scp an initialization script over, and then ssh into the pi and execute it
- **NOTE**: Currently all users have sudo powers.
- **NOTE**: At this point the user should be able to ssh in with ssh USERNAME@ADDRESS_OF_PI.
- **NOTE**: The ADDRESS_OF_PI should be visible in the manifest rspec returned after provisioning.
- **NOTE**: The user should not have to enter a password, but may have to accept the keys with "yes".
- **NOTE**: If necessary, ssh -i /path/to/specific/key USERNAME@ADDRESS_OF_PI.
- **NOTE**: Installing XQuarts or another terminal software and using ssh -X grants increased functionality.
10. Delete slice
- 1. python omni.py -V 3 -a http://128.89.91.170:7010 delete <slicename>
- **NOTE**: The above command will delete all slivers in the slice.
- **NOTE**: BosController executes a script on the provision server, which erases the specified client nfs, rsyncs a clean backup, replaces the specifed /etc/network/interfaces file, and then uses minicom to reboot the pi.
- **NOTE**: If the directory structure is modified, the command syntax may need to be adjusted accordingly.
- **NOTE**: It will also re-adjust the current state of pis and make them able to be allocated once again.

### Additional Notes

- **NOTE**: Again, currently all users have sudo access.
- **NOTE**: When this sliver is deleted, your ssh access will be deleted.
- **NOTE**: If your slivers expire, or the AM or CH shuts down, before you delete the slice: you may need to create the slice again, allocate an unallocated node to that slice, and then delete that slice, it should clear up all of the nodes as well as the pi on which you were working on.
- **DEV-NOTE**: Additionally, the rpi_config file or the snapshot can be hard-edited, and must be if an additional pi is added.
- **DEV-NOTE**: Only the availability and owner are dumped/restored via snapshots, using the persistent state attribute
- **DEV-NOTE**: eth0 is always the actual ethernet port.
- **DEV-NOTE**: The USB ports are labeled from eth1-eth4 in the order of top left, bottom left, top right, bottom right, upon reboot.
- **DEV-NOTE**: The ip address of the provision server is referenced in the provision_interface.py file.
- **DEV-NOTE**: The ip addresses of the pis are hard coded into the rpi_config.json file.
- **DEV-NOTE**: When changing ip addresses, be careful to change the dnsmasq.conf file, the tftpboot directory names, the tftpboot/IP_ADDRESS/cmdline.txt nfs root reference, and/or the backupint/clientX /etc/network/interfaces file.
- **DEV-NOTE**: To use minicom, that user must be added to the dialout group

- **DEV-NOTE**: The directories on the provision server that are used are:
- **DEV-NOTE**: NFS: Holds all the file systems
- **DEV-NOTE**: tftpboot: Holds all the boot files, sorted by ip address
- **DEV-NOTE**: backupint: Holds the /etc/network/interfaces files used during reboot to differentiate ip addresses
- **DEV-NOTE**: tempgram: Holds the minicom scripts as well as the script used during provision (provision.sh)
- **DEV-NOTE**: /etc/minicom: Holds the minicom rc files used by gram
