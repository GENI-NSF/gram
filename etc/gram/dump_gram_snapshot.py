# Tool to dump the state of a gram snapshot
import json
import optparse
import os
import sys

def parse_args(argv=None):
    if argv==None: argv=sys.argv
    parser = optparse.OptionParser()
    parser.add_option("--directory", dest="directory", default=None,
                          help="Name of directory from which to choose most recent snapshot")
    parser.add_option("--snapshot", dest="snapshot", default=None, \
                          help="Name of snapshot file form which to read GRAM state")

    return parser.parse_args(argv)

def main():
    opts, args = parse_args(sys.argv)

    if not opts.directory and not opts.snapshot:
        print "Usage: dump_gram_snapshot --directory <dir> --snapshot <snap>"
        return 0

    snapshot = opts.snapshot
    if not opts.snapshot:
        dir = opts.directory
        files = [os.path.join(dir, s) for s in os.listdir(dir) 
                 if os.path.isfile(os.path.join(dir, s))]
        files.sort(key = lambda s: os.path.getmtime(s))
        snapshot = files[len(files)-1]

    raw_data = open(snapshot, 'r').read()
    json_data = json.loads(raw_data)

    # JSON slice data by slice URN
    json_slices = {}

    # JSON sliver data by sliver URN
    json_slivers = {}
    
    for json_object in json_data:
        if json_object['__type__'] == 'Slice':
            slice_urn = json_object['slice_urn']
            json_slices[slice_urn] = json_object
        else:
            sliver_urn = json_object['sliver_urn']
            json_slivers[sliver_urn] = json_object

    print "Dumping snapshot %s:" % snapshot
    for slice_urn in json_slices:
        slice_obj = json_slices[slice_urn]
        print "Slice %s" % (slice_urn)
        slivers = slice_obj['slivers']
        for sliver_urn in slivers:
            sliver_object = json_slivers[sliver_urn]
            sliver_user_urn = sliver_object['user_urn']
            print "   Sliver %s User: %s" % (sliver_urn, sliver_user_urn)




if __name__ == "__main__":
    sys.exit(main())

    
