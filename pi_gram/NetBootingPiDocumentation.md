# NetBoot Pi Documentation:

### How to Boot Raspberry Pi 3s Using dnsmasq as your DHCP and TFTP Server.

#### Step 1: SD Card Set-Up: (Use any SD card on any PC)
- Clean and format the SD Card, should be at least 8 GB, use MS DOS FAT format.
- Download Noobs, or whichever image (currently successfully tested for Raspbian and Raspbian Lite, unsuccessful for Kano).

#### Step 2: Initial Server Set-Up: (On a Raspberry Pi or Linux PC)
- sudo mkdir /tftpboot
- sudo chmod 777 /tftpboot
- sudo mkdir /tftpbootbackup
- sudo 777 chmod /tftpbootbackup
- sudo mkdir /nfs/clientbackup
- If you want a static ip address, such as 10.42.0.212:
  - sudo nano /etc/network/interfaces
  - replace "iface eth0 inet manual" with:
  - auto eno1 (or whatever you choose)
  - iface eno1 inet static
  - address 10.42.0.212 (or whatever you choose)
  - netmask 255.255.255.0

#### Step 3: Create the original NFS: (On any Raspberry Pi 3 with the formatted SD card)
- Install the OS.
- sudo apt-get update && sudo apt-get upgrade
- sudo raspi-config and expand the root file system to take up the entire SD card, this is automatically done on NOOBS
- **NOTE**: If you want SSH:
- **NOTE**: sudo update-rc.d ssh defaults
- **NOTE**: sudo update-rc.d ssh enable
- **NOTE**: sudo service ssh start
- **NOTE**: Now if you ssh in and add your key to the authorized_keys directory before creating this backup, you will have access to each client
- sudo mkdir -p /nfs/client
- sudo apt-get install rsync
- **NOTE**: If there are additional software packages that you would like installed on every client that you use, now would be the best time to install them
- **NOTE**: These next three rsyncs may take some time (well, not the tftpboot one), but they only have to be done once each
- **NOTE**: The clientbackup and tftpbootbackup will remain your pristine copies
- sudo rsync -xa --progress --exclude /nfs / /nfs/clientbackup
- sudo rsync -ra /nfs/clientbackup root@SERVER_IP_ADDRESS:/nfs/clientbackup
- sudo rsync -ra /boot/* root@SERVER_IP_ADDRESS:/tftpbootbackup

#### Step 4: Client-side set up: (On each Raspberry Pi 3 that you would like to be a client, with the sd card)
- ifconfig
- Make note of the MAC/HW address of the ethernet port of the pi, PI_MAC_ADD
- sudo nano /boot/config.txt and add "program_usb_boot_mode=1" to the bottom
- sudo reboot
- vcgencmd otp_dump | grep 17:
- ensure the output is 0x3020000a
- Remove the program_usb_boot_mode=1 from the /boot/config.txt
- Remove the SD card from the pi. It should no longer be necessary!

#### Step 5: Server Pre-Configuration: (On your server)
- sudo apt-get update
- sudo apt-get install rsync
- sudo apt-get install dnsmasq
- sudo apt-get install tcpdump
- sudo apt-get install nfs-kernel-server
- sudo rm /etc/resolvconf/update.d/dnsmasq
- sudo systemctl disable dhcpcd
- sudo systemctl enable networking
- sudo reboot

#### Step 6: Server dnsmasq Configuration: (On your server)
- sudo nano /etc/dnsmasq.conf
- remove everything in dnsmasq.conf file
- Add the following lines:
  - interface=eno1 (or whatever you named it)
  - port=0
  - log-dhcp
  - enable-tftp
  - dhcp-boot=bootcode.bin
  - tftp-root=/tftpboot
  - pxe-service=0,"Raspberry Pi Boot"
  - tftp-unique-root    (This allows for a separate tftproot based on ip address)
  - dhcp-option=3       (This disables the dhcp server from advertising as the default gateway)
  - dhcp-range=10.42.0.10, 10.42.0.100, 6h (customize as needed)
  - dhcp-host=PI_MAC_ADDRESS,IP_ADDRESS_TO_BE_ASSIGNED (i.e. dhcp-host=b8:27:eb:43:97:10,10.42.0.101)
  - ^ repeat the above line for each pi that is to be a client, using their MAC address and a chosen ip address to be assigned
- sudo systemctl enable dnsmasq.service
- sudo ststemctl restart dnsmasq.service

#### Step 7: Server NFS Configuration: (On your server)
- sudo nano /nfs/clientbackup/etc/network/interfaces
- add the following three lines to create an additional interface, to be used with a USB to Ethernet dongle
  - auto eth1
  - allow-hotplug eth1
  - iface eth1 inet dhcp
- sudo nano /nfs/clientbackup/etc/fstab and remove /dev/mmcbkp1 and /dev/mmcbkp2 lines, leaving only proc
- Now make an /nfs/client directory for each pi, i.e. /nfs/client1 and /nfs/client2
- rsync the contents of /nfs/clientbackup into each of the other /nfs/clientX directories

#### Step 8: Server TFTPBOOT Configuration: (On your server)
- Each pi has now been assigned an ip address based on its MAC address
- Create a directory in /tftpboot for each IP address that was assigned i.e. /tftpboot/10.42.0.101 and /tftpboot/10.42.0.102 and so on
- Copy the contents of /tftpbootbackup into each of the /tftpboot/IP_ADDRESS directories
- In each /tftpboot/IP_ADDRESS directory, you will find a cmdline.txt file
- edit each file:
- from root= onwards, replace it with
  - root=/dev/nfs nfsroot=10.42.0.212:/nfs/client1 rw ip=dhcp rootwait elevator=deadline
  - replace 10.42.0.212 with your server ip address and replace /nfs/client1 with whichever client directory you created for it
  - Make sure each pi has its own /nfs/client directory and that it is properly specified in the cmdline.txt nfsroot argument
- for each /nfs/clientX directory created:
- echo "/nfs/clientX *(rw,sync,no_subtree_check,no_root_squash)" | sudo tee -a /etc/exports
- sudo systemctl enable rpcbind
- sudo systemctl restart rpcbind
- sudo systemctl enable nfs-kernel-server
- sudo systemctl restart nfs-kernel-server
- **NOTE**: Restart the nfs-kernel-server anytime the exports file is edited.

### Additional Documentation
- Use one ethernet switch to connect the client pis to the server, and one ethernet switch to connect the client pis to the internet.
- It is possible to use a Remote Power Strip such as RPB+, and communicate via Minicom to powercycle the pis.

#### If you want to use Static IP Addresses for the Public-facing Side
- Underneath the "allow hotplug eth1" of the nfs/clientX/etc/network/interfaces file, add:
  - address x.x.x.x
  - netmask x.x.x.x
  - gateway x.x.x.x
  - dns-nameservers x.x.x.x y.y.y.y
  - dns-search website.com

#### To Clean with the Same Image
- sudo rm -rf /nfs/clientX
- mkdir /nfs/clientX
- sudo rsync -ra /nfs/clientbackup/* /nfs/clientX

#### To Clean with a New Image
- Place that image's boot files in the specified /tftpboot/IP_ADDRESS subdirectory.
- Make sure the cmdline.txt is specified to the proper /nfs/clientX file system.
- Follow the above cleaning steps. You may need to have a backup for each type of image if the NFS is vastly different.

#### When Adding a New Pi Client
- Using the SD card, make sure USB Boot Mode is enabled (as shown above), and record the MAC address of the pi.
- Append a dnsmasq line assigning an IP address based on that MAC address.
- Create a tftpboot subdirectory with that IP address, and copy tftpbackup into it.
- Edit cmdline.txt to point to a new nfs client.
- Create that new nfs client via rsync from the client backup.
- Add the new nfs client path to the exports file.
- Restart dnsmasq and nfs-kernel-server.

#### Helpful Sites
- https://github.com/raspberrypi/documentation/blob/master/hardware/raspberrypi/bootmodes/net_tutorial.md
- https://docs.oracle.com/cd/E37670_01/E41137/html/ol-dnsmasq-conf.html
- http://docs.slackware.com/howtos:network_services:dhcp_server_via_dnsmasq
- http://www.thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html
- https://superuser.com/questions/306121/i-dont-want-my-dhcp-to-be-a-default-gateway
