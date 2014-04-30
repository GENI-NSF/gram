import glob
import json
import os
import sys

def find_latest_snapshot():
    SNAPSHOT_DIRECTORY = '/etc/gram/snapshots/gram'
    files = glob.glob(SNAPSHOT_DIRECTORY + "/" + "*.json")
    latest_snapshot = None
    latest_ctime = None
    for file in files:
        stat = os.stat(file)
        ctime = stat.st_ctime
        if latest_snapshot is None or latest_ctime < ctime:
            latest_snapshot = file
            latest_ctime = ctime
    return latest_snapshot

def parse_snapshot(snapshot_filename):
    snapshot_data = None
    with open(snapshot_filename, 'r') as snapshot_file:
        snapshot_data = json.load(snapshot_file)
#        print "DATA = %s" % snapshot_data
    objects_by_urn = {}
    objects_by_uid = {}
    if snapshot_data is not None:
        for object in snapshot_data:
            if "__type__" in object:
                obj_type = object['__type__']
                if obj_type == 'Slice':
                    urn = object['slice_urn']
                    uid = object['tenant_uuid']
                    object['slice'] = uid
                elif obj_type in ['VirtualMachine', 'NetworkInterface', \
                                      'NetworkLink']:
                    urn = object['sliver_urn']
                    uid = object['uuid']

                if urn is not None and uid is not None:
                    objects_by_urn[urn] = object
                    objects_by_uid[uid] = object

    # Connect slice uuid into slice_urn
    for obj_urn, obj_attributes in objects_by_urn.items():
        slice_uid = obj_attributes['slice']
        if slice_uid is not None:
            slice = objects_by_uid[slice_uid]
            slice_urn = slice['slice_urn']
            obj_attributes['slice_urn'] = slice_urn

    # Set up hosts for interfaces from associated VM
    for obj_urn, obj_attributes in objects_by_urn.items():
        if obj_attributes['__type__'] == 'NetworkInterface':
            vm_urn = obj_attributes['virtual_machine']
            vm_attributes = objects_by_urn[vm_urn]
            vm_host = vm_attributes['host']
            obj_attributes['host'] = vm_host

    return objects_by_urn

def main():
    latest_snapshot = find_latest_snapshot()
    objects_by_urn = parse_snapshot(latest_snapshot)

    for obj_urn, obj_attributes in objects_by_urn.items():
        expiration = obj_attributes['expiration']
        slice_uid = obj_attributes['slice']
        obj_type = obj_attributes['type']
        slice_urn = obj_attributes['slice_urn']
        print "TYPE %s URN %s SLICE %s EXP %s" % \
            (obj_type, obj_urn, slice_urn, expiration)

if __name__ == "__main__":
    sys.exit(main())

