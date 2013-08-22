#!/bin/bash

if [ "$1" = "-n" ]; then
    checkonly=true
fi

uname=`whoami`

ports=`quantum port-list | grep ip_address | awk '{print $2}' | cut -c1-11`

function portExists() {
    if [ -z "$1" ]; then
        return
    fi

    if [ -z "$2" ]; then
        return
    fi

    pref=$2

    for i in ${ports[@]}; do
        if [ "${pref}${i}" == "$1" ]; then
            echo "Found $1"
            return 0 
        fi
    done

    return 1 
}

qvoovsports=`sudo ovs-vsctl show | grep Interface | grep qvo | awk '{print $2}' | sed -e 's/\"//g'`

for o in $qvoovsports; do
    if ( ! portExists ${o} "qvo" ); then
       echo "Cleaning up port $o" 
       if [ ! $checkonly ]; then
           echo "Removing port"
           sudo ovs-vsctl del-port br-int ${o}
       fi
    fi
done 

tapovsports=`sudo ovs-vsctl show | grep Interface | grep tap | awk '{print $2}' | sed -e 's/\"//g'`

for o in $tapovsports; do
    if ( ! portExists ${o} "tap" ); then
       echo "Cleaning up port $o" 
       if [ ! $checkonly ]; then
           echo "Removing port"
           sudo ovs-vsctl del-port br-int ${o}
       fi
    fi
done 

qrovsports=`sudo ovs-vsctl show | grep Interface | grep "qr-" | awk '{print $2}' | sed -e 's/\"//g'`

for o in $qrovsports; do
    if ( ! portExists ${o} "qr-" ); then
       echo "Cleaning up port $o" 
       if [ ! $checkonly ]; then
           echo "Removing port"
           sudo ovs-vsctl del-port br-int ${o}
       fi
    fi
done 

ifs=`ifconfig -a | grep qvo  | awk '{print $1}'`
for f in $ifs; do 
    if ( ! portExists ${f} "qvo" ); then
       echo "Cleaning up interface $f" 
       if [ ! $checkonly ]; then
           echo "Removing port"
           sudo ip link delete $f 
       fi
    fi
done 

ifs=`ifconfig -a | grep qbr  | awk '{print $1}'`
for f in $ifs; do 
    if ( ! portExists ${f} "qbr" ); then
       echo "Cleaning up interface $f" 
       if [ ! $checkonly ]; then
           echo "Removing port"
           sudo ip link delete $f 
       fi
    fi
done 

ifs=`ifconfig -a | grep tap  | awk '{print $1}'`
for f in $ifs; do 
    if ( ! portExists ${f} "tap" ); then
       echo "Cleaning up interface $f" 
       if [ ! $checkonly ]; then
           echo "Removing port"
           sudo ip link delete $f 
       fi
    fi
done 

ifs=`ifconfig -a | grep "qr-"  | awk '{print $1}'`
for f in $ifs; do 
    if ( ! portExists ${f} "qr-" ); then
       echo "Cleaning up interface $f" 
       if [ ! $checkonly ]; then
           echo "Removing port"
           sudo ip link delete $f 
       fi
    fi
done 
