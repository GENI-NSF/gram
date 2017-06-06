#!/usr/bin/python

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
"""
Framework to run a GENI Aggregate Manager. See geni/am for the 
Reference Aggregate Manager that this runs.

Run with "-h" flag to see usage and command line options.
"""

import importlib
import pdb
import sys
import subprocess
import time

# Check python version. Requires 2.6 or greater, but less than 3.
if sys.version_info < (2, 6):
    raise Exception('Must use python 2.6 or greater.')
elif sys.version_info >= (3,):
    raise Exception('Not python 3 ready')

import threading
import logging
import optparse
import os
import gcf.geni
import gram
import gram.am
import gram.am.am3
import gram.am.gram_am2
import gram.am.gram.config
from gcf.geni.config import read_config

# Return an instance of a class given by fully qualified name                   
# (module_path.classname)                                                       
# Return an instance of a class given by fully qualified name
# (module_path.classname) with variable constructor args
def getInstanceFromClassname(class_name, *argv):
    class_module_name = ".".join(class_name.split('.')[:-1])
    class_base_name = class_name.split('.')[-1]
    class_module = importlib.import_module(class_module_name)
    class_instance = eval("class_module.%s" % class_base_name)
    object_instance = class_instance(*argv)
    return object_instance

# Set up parser and return parsed argumetns
def parse_args(argv):
    parser = optparse.OptionParser()
    parser.add_option("-k", "--keyfile",
                      help="AM key file name", metavar="FILE")
    parser.add_option("-g", "--certfile",
                      help="AM certificate file name (PEM format)", metavar="FILE")
    parser.add_option("-c", "--configfile",  help="config file path", metavar="FILE")
    # Note: The trusted CH certificates are _not_ enough here.
    # It needs self signed certificates. EG CA certificates.
    parser.add_option("-r", "--rootcadir",
                      help="Trusted Root certificates directory (files in PEM format)", metavar="FILE")
    # Could try to determine the real IP Address instead of the loopback
    # using socket.gethostbyname(socket.gethostname())
    parser.add_option("-H", "--host", 
                      help="server ip", metavar="HOST")
    parser.add_option("-p", "--v3_port", type=int, 
                      help="V3 server port", metavar="PORT")
    parser.add_option("-q", "--v2_port", type=int,
                      help="V2 server port", metavar="PORT")
    parser.add_option("--debug", action="store_true", default=False,
                       help="enable debugging output")
    parser.add_option("-V", "--api-version", type=int,
                      help="AM API Version", default=3)
    parser.add_option("--snapshot_dir", \
                          help="name of directory to save snapshots", \
                          default=None)
    parser.add_option("--recover_from_snapshot", \
                          help="name of snapshot to initialize gram state", \
                          default=None)
    parser.add_option("--recover_from_most_recent_snapshot", \
                          help="whether to recover from most recent " + \
                      "snapshot in 'gram_snapshot_directory'", \
                          default=True)
    parser.add_option("--snapshot_maintain_limit", type=int,
                          help="Retain only this limit of recent snapshots",
                          default=10)
    parser.add_option("--config_file", 
                      help="Location of GRAM installation-specific " + 
                      "configuration", 
                      default="/etc/gram/config.json")
    return parser.parse_args()

def getAbsPath(path):
    """Return None or a normalized absolute path version of the argument string.
    Does not check that the path exists."""
    if path is None:
        return None
    if path.strip() == "":
        return None
    path = os.path.normcase(os.path.expanduser(path))
    if os.path.isabs(path):
        return path
    else:
        return os.path.abspath(path)

def main(argv=None):
    if argv is None:
        argv = sys.argv
    opts = parse_args(argv)[0]


    gram.am.gram.config.initialize(opts.config_file)

    # If the port isn't set explicitly, use defaults from config
    if not opts.v3_port:
        opts.v3_port = gram.am.gram.config.gram_am_port
    if not opts.v2_port:
        opts.v2_port = gram.am.gram.config.gram_am_v2_port

    level = logging.INFO
    if opts.debug:
        level = logging.DEBUG
    logging.basicConfig(level=level, format = '%(asctime)s %(message)s')

    # Read in config file options, command line gets priority
    optspath = None
    if not opts.configfile is None:
        optspath = os.path.expanduser(opts.configfile)

    config = read_config(optspath)   
        
    for (key,val) in config['aggregate_manager'].items():                  
        if hasattr(opts,key) and getattr(opts,key) is None:
            setattr(opts,key,val)
        if not hasattr(opts,key):
            setattr(opts,key,val)            
    if getattr(opts,'rootcadir') is None:
        setattr(opts,'rootcadir',config['global']['rootcadir'])        

    if opts.rootcadir is None:
        sys.exit('Missing path to trusted root certificate directory (-r argument)')
    
    certfile = getAbsPath(opts.certfile)
    keyfile = getAbsPath(opts.keyfile)
    if not os.path.exists(certfile):
        sys.exit("Aggregate certfile %s doesn't exist" % certfile)
    
    if not os.path.exists(keyfile):
        sys.exit("Aggregate keyfile %s doesn't exist" % keyfile)

    # Check if quantum is running, if not, then take a nap
    command_str = '%s net-list' % gram.am.gram.config.network_type
    command = command_str.split()
    ready = 0
    while(not ready):
        try :
            subprocess.check_output(command)
            ready = 1
            logging.getLogger('gram-am').info(' Ready to start GRAM')
        except :
            logging.getLogger('gram-am').error('Error executing command %s' % command)
            time.sleep(15)

    gram.am.gram.config.snapshot_dir = opts.snapshot_dir
    gram.am.gram.config.recover_from_snapshot = opts.recover_from_snapshot
    gram.am.gram.config.recover_from_most_recent_snapshot = \
        opts.recover_from_most_recent_snapshot
    gram.am.gram.config.snapshot_maintain_limit = opts.snapshot_maintain_limit

    # Instantiate an argument guard that will reject or modify                  
    # arguments and options provided to calls                                   
    argument_guard = None
    if hasattr(opts, 'argument_guard'):
        argument_guard = getInstanceFromClassname(opts.argument_guard)

   # Instantiate authorizer from 'authorizer' config argument                  
   # By default, use the SFA authorizer                                        
    if hasattr(opts, 'authorizer'):
        authorizer_classname = opts.authorizer
    else:
        authorizer_classname = "gcf.geni.auth.sfa_authorizer.SFA_Authorizer"
    authorizer = getInstanceFromClassname(authorizer_classname,
                                          opts.rootcadir, opts, argument_guard)

    # Use XMLRPC authorizer if opt.remote_authorizer is set                     
    if hasattr(opts, 'remote_authorizer'):
        import xmlrpclib
        authorizer = xmlrpclib.Server(opts.remote_authorizer)

    # Instantiate resource manager from 'authorizer_resource_manager'           
    # config argument. Default = None                                           
    resource_manager = None
    if hasattr(opts, 'authorizer_resource_manager'):
        resource_manager = \
            getInstanceFromClassname(opts.authorizer_resource_manager)

    # rootcadir is  dir of multiple certificates
    delegate = gcf.geni.ReferenceAggregateManager(getAbsPath(opts.rootcadir))

    # here rootcadir is supposed to be a single file with multiple
    # certs possibly concatenated together
    comboCertsFile = gcf.geni.CredentialVerifier.getCAsFileFromDir(getAbsPath(opts.rootcadir))

    server_url = "https://%s:%d/" % (opts.host, int(opts.v3_port))
    GRAM=gram.am.am3.GramReferenceAggregateManager(getAbsPath(opts.rootcadir), config['global']['base_name'], certfile, server_url)

    if opts.api_version == 1:
        msg = "Version 1 of AM API unsopported in GRAM"
        sys.exit(msg)
    #elif opts.api_version == 2:
    ams_v2 = gram.am.gram_am2.GramAggregateManagerServer((opts.host, int(opts.v2_port)),
                                          keyfile=keyfile,
                                          certfile=certfile,
                                          trust_roots_dir=getAbsPath(opts.rootcadir),
                                          ca_certs=comboCertsFile,
                                          base_name=config['global']['base_name'],
                                          authorizer=authorizer,
                                          resource_manager = resource_manager,
                                          GRAM=GRAM)
    #elif opts.api_version == 3:
    ams_v3 = gram.am.am3.GramAggregateManagerServer((opts.host, int(opts.v3_port)),
                                          keyfile=keyfile,
                                          certfile=certfile,
                                          trust_roots_dir=getAbsPath(opts.rootcadir),
                                          ca_certs=comboCertsFile,
                                          base_name=config['global']['base_name'],
                                          authorizer=authorizer,
                                          resource_manager = resource_manager,
                                          GRAM=GRAM)
    #else:
    #    msg = "Unknown API version: %d. Valid choices are \"1\", \"2\", or \"3\""
    #    sys.exit(msg % (opts.api_version))

    logging.getLogger('gcf-am').info('GENI AM 3 Listening on port %s...' % (opts.v3_port))
    logging.getLogger('gcf-am').info('GENI AM 2 Listening on port %s...' % (opts.v2_port))
 
    thread = threading.Thread(target=ams_v2.serve_forever,args=())
    thread.start()
    ams_v3.serve_forever()

if __name__ == "__main__":
    sys.exit(main())
