#----------------------------------------------------------------------
# Copyright (c) 2011-2014 Raytheon BBN Technologies
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

# Module to populate monitoring database with live statistics of
# State of all the compute nodes on this rack

import gram_slice_info
import json
import os
import psutil
import subprocess
import sys
import tempfile
import time

opsmon_path='/home/gram/ops-monitoring'
local_path = opsmon_path + "/local"
common_path = opsmon_path + "/common"
config_path = opsmon_path + "/config"

sys.path.append(opsmon_path)
sys.path.append(local_path)
sys.path.append(common_path)
sys.path.append(config_path)

import table_manager

# Class to generate data files representing current selected states
# on all compute hosts, and populate database tables accordingly
# Maintains a rolling window of data, deleting elements older than a given
# time before present
class OpsMonPopulator:
    def __init__(self, config):
        self._frequency_sec = int(config['frequency_sec'])
        self._window_duration_sec = int(config['window_duration_sec'])
        self._database_user = config['database_user']
        self._database_pwd = config['database_pwd']
        self._database_name = config['database_name']

        # External IP addr of Gram rack local datastore
        self._base_url = config['base_address']

        self._aggregate_id = config['aggregate_id']
        self._aggregate_urn = config['aggregate_urn']

        # Aggregate info query url
        self._aggregate_href = self._base_url + "/info/aggregate/" + self._aggregate_id

        # Time-series data measurement reference
        self._measurement_href = self._base_url + "/data/"

        self._hosts = config['hosts']
        self._modules = config['modules']
        self._commands = config['commands']
        self._interface_commands = config['interface_commands']

        self._prev_values = {}
        self._config = config
        self._table_manager = table_manager.TableManager('local', config_path, False)
        for cmd in self._commands:
            tablename = cmd['table']
            self._prev_values[tablename] = {}

        # json-schema
        self._agg_schema = "http://www.gpolab.bbn.com/monitoring/schema/20140131/aggregate#"
        self._node_schema = "http://unis.incntre.iu.edu/schema/20120709/node#"
        self._sliver_schema = "http://www.gpolab.bbn.com/monitoring/schema/20140131/sliver#"
        self._interface_schema = "http://www.gpolab.bbn.com/monitoring/schema/20140131/interface#"

        # Change ' to " in any expressions (can't parse " in json)
        for cmd in self._commands:
            expr = cmd['expression']
            expr_new = expr.replace("'", '\\"')
            cmd['expression'] = expr_new

        imports = ";".join("import %s" % mod for mod in self._modules)
        measurements = ", ".join(c['expression'] for c in self._commands)
        self._rsh_command = "python -c %s%s;print %s%s" % \
            ('"', imports, measurements, '"')
#        print "RSH =  %s" % self._rsh_command
        self._interface_info_rsh_command = "python -c %s%s%s;print %s%s" % \
            ('"', imports, ';import json', 'json.dumps(psutil.net_io_counters(pernic=True))', '"')
#        print "IFACE RSH =  %s" % self._interface_info_rsh_command

        self._nodes = {}
        self._initialize_nodes()

    # setting the nodes dictionary using dense code format 
    def _initialize_nodes(self):
        for node in self._config['hosts']:
            node_id = self.get_node_id(node['id'])
            node_urn = node['urn']

            node_address = node['address']
            imports = "import psutil"
            measurements = "psutil.virtual_memory().total/1000"
            rsh_memory_command = "python -c%s%s;print %s%s" % \
                ('"', imports, measurements, '"')

            rsh_command = ['rsh', node_address, rsh_memory_command]
            result = subprocess.check_output(rsh_command)
            mem_total_kb = int(result)
                       
            node_url = "%s/info/node/%s" % (self._base_url, node_id)
            self._nodes[node_id] = {'id':node_id, 'urn': node_urn, 
                              'href': node_url, 'mem_total_kb': mem_total_kb, 
                              'schema': self._node_schema}

    def get_node_id(self, node_name):
        return self._aggregate_id + "." + node_name
    
    def get_interface_id(self, node_urn, interface_name):
        return flatten_urn(node_urn + "_" + interface_name)

    # Top-level loop: Generate data file, execute into database and sleep
    def run(self):
        self.update_info_tables()
        print "Updated OpsMon static info for %s at %d" % (self._aggregate_id, int(time.time()))
        while True:
            self.update_data_tables()
            self.update_sliver_tables()
#            data_filename = self.generate_data_file()
#            self.execute_data_file(data_filename)
#            print "FILE = %s" % data_filename
#            os.unlink(data_filename)
            print "Updated OpsMon dynamic data for %s at %d" % (self._aggregate_id, int(time.time()))
            time.sleep(self._frequency_sec)

    # Update static H/W config information based on config plus information
    # from nodes themselves
    def update_info_tables(self):
        self.update_node_info()
        self.update_interface_info()

    # Update node info tables
    def update_node_info(self):
        ts = str(int(time.time()*1000000))
        for node_id, nd in self._nodes.items():
            node = [nd['schema'], nd['id'], nd['href'], nd['urn'], ts, nd['mem_total_kb']]
            info_insert(self._table_manager, "ops_node", node)

    # Update interface info tables
    def update_interface_info(self):
        ts = str(int(time.time()*1000000))

        # Clear out old interface info:
        self._table_manager.purge_old_tsdata('ops_interface', ts)
        # Clear out old sliver resource info
        for node_urn, node_info in self._nodes.items():
            node_id = self.get_node_id(node_info['id'])
            self._table_manager.delete_stmt('ops_node_interface', node_id)

        # Insert into ops_node_interface
        for node_info in self._config['hosts']:
            node_urn = node_info['urn']
            node_id = self.get_node_id(node_info['id'])
            for iface_name, iface_data in node_info['interfaces'].items():
                iface_id = self.get_interface_id(node_urn, iface_name)
                iface_urn = node_urn + ":" + iface_name
                iface_href = self._base_url + "/info/interface/" + iface_id
                node_interface_info = [iface_id, node_id, iface_urn, iface_href]
                info_insert(self._table_manager, 'ops_node_interface', node_interface_info)

                iface_address = iface_data['address']
                iface_role = iface_data['role']
                iface_address_type = iface_data['type']
                iface_max_bps = iface_data['max_bps']
                iface_max_pps = 0

                interface_info = [self._interface_schema, iface_id, iface_href, iface_urn, \
                                      ts, iface_address_type, \
                                      iface_address, iface_role, iface_max_bps, iface_max_pps]
                info_insert(self._table_manager, 'ops_interface', interface_info)

    # Update sliver tables based on most recent snapshot
    def update_sliver_tables(self):
        ts = int(time.time()*1000000)

        # Clear out old sliver info:
        self._table_manager.purge_old_tsdata('ops_sliver', ts)
        # Clear out old sliver resource info
        for node_urn, node_info in self._nodes.items():
            node_id = node_info['id']
            self._table_manager.delete_stmt('ops_sliver_resource', node_id)

        latest_snapshot = gram_slice_info.find_latest_snapshot()
        objects_by_urn = gram_slice_info.parse_snapshot(latest_snapshot)

        # Insert into ops_sliver_resource table and ops_aggregate_sliver table
        for object_urn, object_attributes in objects_by_urn.items():
            if object_attributes['type'] not in ['NetworkInterface', 'VirtualMachine']: continue
            slice_urn = object_attributes['slice_urn']
            sliver_id = flatten_urn(slice_urn) + "_" + object_attributes['name']
        
            # Insert into sliver tables
        for object_urn, object_attributes in objects_by_urn.items():
            if object_attributes['type'] not in ['NetworkInterface', 'VirtualMachine']: continue
            schema = self._sliver_schema
            slice_urn = object_attributes['slice_urn']
            sliver_id = flatten_urn(slice_urn) + "_" + object_attributes['name']
            sliver_href = self._base_url + '/info/sliver/' + sliver_id
            sliver_urn = object_urn
            sliver_uuid = object_attributes['uuid']
            slice_urn = object_attributes['slice_urn']
            slice_uuid = object_attributes['slice']
            creator = object_attributes['user_urn']
            created = object_attributes['creation']
            expires = object_attributes['expiration']
            if expires is None: expires = -1
            node_name = object_attributes['host']
            node_id = self._aggregate_id + "." + node_name
            node_urn = None
            for node in self._config['hosts']:
                if node['id'] == node_name: node_urn = node['urn']
                node_href = self._base_url + "/info/sliver_resource/" + node_id

            # Insert into ops_sliver_table
            sliver_info = [schema, sliver_id, sliver_href, sliver_urn, sliver_uuid, \
                               ts, self._aggregate_urn, self._aggregate_href, \
                               slice_urn, slice_uuid, creator, \
                               created, expires]
            info_insert(self._table_manager, 'ops_sliver', sliver_info)

            # Insert into ops_sliver_resource table
            sliver_resource_info = [node_id, sliver_id, node_urn, node_href]
            info_insert(self._table_manager, 'ops_sliver_resource', sliver_resource_info)

            # Insert into ops_aggregate_sliver table
            sliver_aggregate_info = \
                [sliver_id, self._aggregate_id, sliver_urn, sliver_href]
            info_insert(self._table_manager, 'ops_aggregate_sliver', sliver_aggregate_info)


    # Update data tables 
    # Remove old records
    # Grab new entries from hosts
    # and place in appropriate data tables
    def update_data_tables(self):

        ts = int(time.time()*1000000)
        window_threshold = ts - (self._window_duration_sec * 1000000)

        # Delete old records from data tables
        for command in self._commands + self._interface_commands:
            tablename = command['table'] 
            self._table_manager.purge_old_tsdata(tablename, window_threshold)

        # For each host, grab the most recent data in a single command
        for host in self._hosts:

            host_id = self.get_node_id(host['id'])
            node_urn = self._nodes[host_id]['urn']
            host_address = host['address']
            rsh_command = ["rsh", host_address, self._rsh_command]
#            print "RSH = %s" % rsh_command
            result = subprocess.check_output(rsh_command)
#            print "RESULT (%s) = %s" % (host_id, result)
            measurements = result.split(' ')
            for i in range(len(measurements)):
                command = self._commands[i]
                tablename = command['table']
                change_rate = 'change_rate' in command
                value = int(float(measurements[i]))
                # For metrics that are change rates, keep track of previous value
                # And compute rate of change (change in metric / change in time)
                if change_rate:
                    value = self._compute_change_rate(value, tablename, host_id)

                ts_data = [host_id, ts, value]
                info_insert(self._table_manager,  tablename, ts_data)

            interface_info_rsh_command = ['rsh', host_address, self._interface_info_rsh_command]
            interface_info_string = subprocess.check_output(interface_info_rsh_command)
            interface_info = json.loads(interface_info_string)
#            print "II(%s) = %s" % (host_id , interface_info)
            for interface_name, interface in host['interfaces'].items():
                interface_id = self.get_interface_id(node_urn, interface_name)
                for interface_command in self._interface_commands:
                    tablename = interface_command['table']
                    expression = interface_command['expression']
                    expression_index = psutil._common.snetio._fields.index(expression)
                    change_rate = interface_command['change_rate']
                    value = interface_info[interface_name][expression_index]
                    
                    if change_rate:
                        value = self._compute_change_rate(value, tablename, interface_id)

                    ts_data = [interface_id, ts, value]
                    info_insert(self._table_manager, tablename, ts_data)

    def _compute_change_rate(self, value, tablename, identifier):
        prev_value = value # For first time, make change rate zero
        if tablename in self._prev_values and \
                identifier in self._prev_values[tablename]:
            prev_value = self._prev_values[tablename][identifier]
        if tablename not in self._prev_values: self._prev_values[tablename] = {}
        self._prev_values[tablename][identifier] = value
        value = int(((value - prev_value) / float(self._frequency_sec)))
        return value

# Helper functions

 # Replace : and + in URN to -
def flatten_urn(urn):
    return urn.replace(':', '_').replace('+', '_')

# creates a values string from an ordered array of values
def info_insert(table_manager, table_str, row_arr):
    val_str = "('"
        
    for val in row_arr:
        val_str += str(val) + "','" # join won't do this
    val_str = val_str[:-2] + ")" # remove last 2 of 3 chars: ',' and add )

    table_manager.insert_stmt(table_str, val_str)

def main():
    if len(sys.argv) < 2:
        print "Usage: python gram_opsmon_populator config_filename"
        return

    config_filename = sys.argv[1]
    config = None
    with open(config_filename) as config_file:
        config_data = config_file.read()
        config = json.loads(config_data)

    if config is not None:

        required_fields = ['frequency_sec', 'window_duration_sec',
                           'database_user', 'database_pwd', 'database_name', 
                           'hosts', 'modules', 'commands']
        missing_fields = []
        for field in required_fields:
            if field not in config: missing_fields.append(field)
        if len(missing_fields) > 0:
            sys.exit("Missing required fields in config: %s" % missing_fields)

        populator = OpsMonPopulator(config)
        populator.run()
        

if __name__ == "__main__":
    sys.exit(main())

