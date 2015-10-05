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
        self._node_commands = config['node_commands']
        self._interface_commands = config['interface_commands']

        self._prev_values = {}
        self._config = config
        self._table_manager = table_manager.TableManager('local', config_path, False)
        for cmd in self._node_commands:
            tablename = cmd['table']
            self._prev_values[tablename] = {}

        self._gram_config = json.loads(open('/etc/gram/config.json').read())

        self._recent_snapshot = None
        self._objects_by_urn = {} # Current objects read by snapshot

        # json-schema
        self._agg_schema = "http://www.gpolab.bbn.com/monitoring/schema/20140501/aggregate#"
        self._authority_schema = "http://www.gpolab.bbn.com/monitoring/schema/20140501/authority#"
        self._node_schema = "http://www.gpolab.bbn.com/monitoring/schema/20140501/node#"
        self._sliver_schema = "http://www.gpolab.bbn.com/monitoring/schema/20140501/sliver#"
        self._slice_schema = "http://www.gpolab.bbn.com/monitoring/schema/20140501/slice#"
        self._interface_schema = "http://www.gpolab.bbn.com/monitoring/schema/20140501/port#"
        self._interfacevlan_schema = "http://www.gpolab.bbn.com/monitoring/schema/20140501/port-vlan#"
        self._link_schema = "http://www.gpolab.bbn.com/monitoring/schema/20140501/link#"
        self._user_schema = "http://www.gpolab.bbn.com/monitoring/schema/20140501/user#"

        # Change ' to " in any expressions (can't parse " in json)
        for cmd in self._node_commands:
            expr = cmd['expression']
            expr_new = expr.replace("'", '\\"')
            cmd['expression'] = expr_new

        imports = ";".join("import %s" % mod for mod in self._modules)
        measurements = ", ".join(c['expression'] for c in self._node_commands)
        self._rsh_command = "python -c %s%s;print %s%s" % \
            ('"', imports, measurements, '"')
#        print "RSH =  %s" % self._rsh_command
        self._interface_info_rsh_command = "python -c %s%s%s;print %s%s" % \
            ('"', imports, ';import json', 'json.dumps(psutil.net_io_counters(pernic=True))', '"')
#        print "IFACE RSH =  %s" % self._interface_info_rsh_command

        self._external_vlans = self._compute_external_vlans()
        self._internal_vlans = \
            parseVLANs(self._gram_config['internal_vlans'])

        self._nodes = {}
        self._links = {}
        self._initialize_nodes()

    # setting the nodes dictionary using dense code format 
    def _initialize_nodes(self):
        for node in self._config['hosts']:
            hostname = node['id']
            node_id = self.get_node_id(hostname)
            node_urn = node['urn']

            node_address = node['address']
            imports = "import psutil"
            measurements = "psutil.virtual_memory().total/1000"
            rsh_memory_command = "python -c%s%s;print %s%s" % \
                ('"', imports, measurements, '"')

            rsh_command = ['rsh', node_address, rsh_memory_command]
            result = subprocess.check_output(rsh_command)
            mem_total_kb = int(result)
                       
            node_href = self.get_node_href(node_id)
            self._nodes[node_id] = {'id':node_id, 'urn': node_urn, 
                                    'host' : hostname,
                                    'href': node_href, 'mem_total_kb': mem_total_kb, 
                                    'schema': self._node_schema}
            
    def get_node_id(self, node_name):
        return self._aggregate_id + "." + node_name

    def get_slice_id(self, slice_urn):
        return flatten_urn(self._aggregate_id + "." + slice_urn)

    def get_authority_id(self, authority_urn):
        return flatten_urn(authority_urn)

    def get_user_id(self, user_urn):
        return flatten_urn(self._aggregate_id + "." + user_urn)

    def get_link_id(self, link_urn):
        return flatten_urn(link_urn)

    def get_interface_urn(self, node_urn, iface_name):
        return node_urn + ":" + iface_name

    def get_interface_id(self, node_urn, interface_name):
        return flatten_urn(node_urn + "_" + interface_name)

    def get_interfacevlan_id(self, urn):
        return flatten_urn(urn)

    def get_interfacevlan_urn(self, tag):
        return self._aggregate_urn + "_VLANL_" + str(tag)

    def get_node_href(self, node_id):
        return "%s/info/node/%s" % (self._base_url, node_id)
    
    def get_link_href(self, link_id):
        return "%s/info/link/%s" % (self._base_url, link_id)

    def get_interface_href(self, interface_id):
        return self._base_url + "/info/interface/" + interface_id

    def get_interfacevlan_href(self, interfacevlan_id):
        return self._base_url + "/info/interfacevlan/" + interfacevlan_id

    def get_slice_href(self, slice_id):
        return self._base_url + "/info/slice/" + slice_id

    def get_authority_href(self, authority_id):
        return self._base_url + "/info/authority/" + authority_id

    def get_usr_href(self, user_id):
        return self._base_url + "/info/user/" + user_id

    def get_sliver_href(self, sliver_id):
        return self._base_url + "/info/sliver/" + sliver_id

    def get_sliver_resource_href(self, sliver_resource_id):
        node_href = \
            self._base_url + "/info/sliver_resource/" + sliver_resource_id

    def get_internal_link_urn(self):
        return self._aggregate_urn+ "_INTERNAL"

    # Top-level loop: Generate data file, execute into database and sleep
    def run(self):
        print "GRAM OPSMON process for %s" % self._aggregate_id
        while True:
            self._latest_snapshot = gram_slice_info.find_latest_snapshot()
            self._objects_by_urn = gram_slice_info.parse_snapshot(self._latest_snapshot)
            self.delete_static_entries()
            self.update_info_tables()
            self.update_data_tables()
            self.update_slice_tables()
            self.update_sliver_tables()
            self.update_aggregate_tables()
            self.update_interfacevlan_info()
            self.update_switch_info()
#            data_filename = self.generate_data_file()
#            self.execute_data_file(data_filename)
#            print "FILE = %s" % data_filename
#            os.unlink(data_filename)
            print "Updated OpsMon dynamic data for %s at %d" % (self._aggregate_id, int(time.time()))
            time.sleep(self._frequency_sec)

    # Update static H/W config information based on config plus information
    # from nodes themselves
    def update_info_tables(self):
        self.update_aggregate_info()
        self.update_link_info()
        self.update_node_info()
        self.update_interface_info()


    # Update aggregate info tables
    def update_aggregate_info(self):
        ts = str(int(time.time()*1000000))
        self._table_manager.purge_old_tsdata('ops_aggregate', ts)
        meas_ref = self._measurement_href
        agg = [self._agg_schema, self._aggregate_id, self._aggregate_href, self._aggregate_urn, ts, meas_ref]
        info_insert(self._table_manager, 'ops_aggregate', agg)

    def update_link_info(self):
        ts = str(int(time.time()*1000000))
        self._table_manager.purge_old_tsdata('ops_link', ts)

        links = [link for link in self._objects_by_urn.values() \
                     if link['__type__'] == 'NetworkLink']

        for link in links:
            link_urn = link['sliver_urn']
            link_id = self.get_link_id(link_urn)
            link_href = self.get_link_href(link_id)
            link_info = [self._link_schema, link_id, link_href, link_urn, ts]
            info_insert(self._table_manager, 'ops_link', link_info)

            agg_resource_info = [link_id, self._aggregate_id, link_href, link_urn]
            info_insert(self._table_manager, 'ops_aggregate_resource', agg_resource_info)

    # Update node info tables
    def update_node_info(self):
        ts = str(int(time.time()*1000000))
        self._table_manager.purge_old_tsdata('ops_node', ts)
        for node_id, nd in self._nodes.items():
            node = [nd['schema'], nd['id'], nd['href'], nd['urn'], ts, nd['mem_total_kb']]
            resource = [nd['id'], self._aggregate_id, nd['urn'], nd['href']]
            info_insert(self._table_manager, "ops_node", node)
            info_insert(self._table_manager, 'ops_aggregate_resource', resource)

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
                iface_urn = self.get_interface_urn(node_urn, iface_name) 
                iface_href = self.get_interface_href(iface_id)
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

    # Update the ops_link_interface_vlan and ops_interfacevlan
    # tables to reflect current VLAN allocations
    def update_interfacevlan_info(self):
        ts = str(int(time.time()*1000000))
        self._table_manager.purge_old_tsdata('ops_interfacevlan', ts)

        links = [link for link in self._objects_by_urn.values() \
                     if link['__type__'] == 'NetworkLink']
        ifaces = [iface for iface in self._objects_by_urn.values() \
                      if iface['__type__'] == 'NetworkInterface']
        vms = [vm for vm in self._objects_by_urn.values() \
                      if vm['__type__'] == 'VirtualMachine']
        data_interface = self._gram_config['data_interface']

        for iface in ifaces:
            ifacevlan_urn = iface['sliver_urn']
            ifacevlan_id = self.get_interfacevlan_id(ifacevlan_urn)
            ifacevlan_href = self.get_interfacevlan_href(ifacevlan_id)

            # The VM of this interface
            iface_vm = None
            for vm in vms:
                if vm['sliver_urn'] == iface['virtual_machine']:
                    iface_vm = vm
                    break
            host = iface_vm['host']

            # The node_urn for compute node on which VM resides
            node_urn = None
            for node_id, node_info in self._nodes.items():
                if node_info['host'] == host:
                    node_urn = node_info['urn']
                    break

            # *** The physical interface on compute host for this sliver interface
            iface_urn = self.get_interface_urn(node_urn, data_interface)
            iface_id = self.get_interface_id(node_urn, data_interface)
            iface_href = self.get_interface_href(iface_id)

            # Find the link for this interface and grab VLAN tag
            link_urn = iface['link']
            link = None
            for lnk in links: 
                if lnk['sliver_urn'] == link_urn:
                    link = lnk;
                    break
            tag = link['vlan_tag']
            link_id = self.get_link_id(link_urn)

            ifacevlan_info = [self._interfacevlan_schema, ifacevlan_id, 
                              ifacevlan_href, ifacevlan_urn, ts, tag,
                              iface_urn, iface_href]
            
            info_insert(self._table_manager, 'ops_interfacevlan', 
                        ifacevlan_info)

            link_ifacevlan_info = [ifacevlan_id, link_id, ifacevlan_urn, ifacevlan_href]
            info_insert(self._table_manager, 'ops_link_interfacevlan',
                        link_ifacevlan_info)

        # Add in stitching interface vlan info
        for link in links:
            if 'stitching_info' in link and \
                    'vlan_tag' in link['stitching_info']:
                vlan_tag = link['stitching_info']['vlan_tag']
                link_urn = link['sliver_urn']
                link_id = self.get_link_id(link_urn)
                ifacevlan_urn = link['stitching_info']['link']
                ifacevlan_id = self.get_interfacevlan_id(ifacevlan_urn)
                ifacevlan_href = self.get_interfacevlan_href(ifacevlan_id)

                link_ifacevlan_info = [ifacevlan_id, link_id, ifacevlan_urn, ifacevlan_href]
                info_insert(self._table_manager, 'ops_link_interfacevlan', 
                            link_ifacevlan_info);
                
                iface_urn = self.find_iface_urn_for_link_urn(ifacevlan_urn)
                iface_id = self.get_interface_id(iface_urn, 'EGRESS')
                iface_href = self.get_interface_href(iface_id)
                ifacevlan_info = [self._interfacevlan_schema, ifacevlan_id,
                                  ifacevlan_href, ifacevlan_urn, ts, vlan_tag, 
                                  iface_urn, iface_href]
                info_insert(self._table_manager, 'ops_interfacevlan',
                            ifacevlan_info);

    # Return the interface port URN for the given stitching link URN
    def find_iface_urn_for_link_urn(self, link_urn):
#        print "LINK_URN = %s" % link_urn
#        print "SI = %s" % self._gram_config['stitching_info']['edge_points']
        for ep in self._gram_config['stitching_info']['edge_points']:
            if ep['local_link'] == link_urn:
                return ep['port']
        return None
                

    # Update information about the switch, its egress ports
    # And associated measurements (pps, bps, etc)
    def update_switch_info(self):

        ts = str(int(time.time()*1000000))

        # Add entry into ops_node for each switch
        switches = []
        if 'stitching_info' in self._gram_config and \
                'edge_points' in self._gram_config['stitching_info']:

            # Gather all the switches and write unique entry in ops_node
            for ep in self._gram_config['stitching_info']['edge_points']:
                switch_name = ep['local_switch']
                if switch_name not in switches: switches.append(switch_name)
            for switch_name in switches:
                switch_id = self.get_node_id(switch_name)
                switch_href = self.get_node_href(switch_id)
                switch_node_info = [self._node_schema, switch_id, switch_href,\
                                        switch_name, ts, 0] # 0 = mem_total_kb
                info_insert(self._table_manager, 'ops_node', switch_node_info)

            # Enter an interface in the ops_interface for the egress_ports
            # As well as ops_node_interface
            # For each end point, grab info from the switch
            # Use that to determine MAC and line speed as well
            # as whatever measurements are available
            for ep in self._gram_config['stitching_info']['edge_points']:
                switch_name = ep['local_switch']
                switch_id = self.get_node_id(switch_name)
                iface_urn = ep['port']
                
                iface_id = self.get_interface_id(iface_urn, 'EGRESS')
                iface_href = self.get_interface_href(iface_id)
                iface_address_type = 'MAC'
                iface_address = 'de:ad:be:ef' # Default if unknown
                iface_role = 'DATA'
                iface_max_bps = 0 
                iface_max_pps = 0 

                if iface_urn in self._config['ports']:
                    stats_command = self._config['ports'][iface_urn]['command']
                    parser_module = \
                        self._config['ports'][iface_urn]['parser_module']
                    parser = self._config['ports'][iface_urn]['parser']
                    measurements = self._config['ports'][iface_urn]['measurements']
                    iface_raw_stats = subprocess.check_output(stats_command)
#                    print "IFACE_RAW_STATS = %s" % iface_raw_stats
                    exec('import %s' % parser_module)
                    parse_cmd = "%s(iface_raw_stats)" % parser
                    iface_stats = eval(parse_cmd)
 #                   print "IFACE_STATS = %s" % iface_stats
                    iface_max_bps = iface_stats['line_speed']
                    iface_address = iface_stats['mac_address']

                    for meas in measurements:
                        meas_table = meas['table']
                        meas_key = meas['key']
                        meas_change_rate = meas['change_rate']
                        value = iface_stats[meas_key]
                        if meas_change_rate:
                            value = self._compute_change_rate(value, 
                                                              meas_table,
                                                              iface_id)
                            ts_data = [iface_id, ts, value]
                            info_insert(self._table_manager, meas_table, 
                                        ts_data)
                         
                # Insert interface and node_interface entries for egress port
                iface_info = [self._interface_schema, iface_id, iface_href,
                              iface_urn, ts, iface_address_type,
                              iface_address, iface_role, 
                              iface_max_bps, iface_max_pps]
                info_insert(self._table_manager, 'ops_interface', iface_info)
                node_iface_info = [iface_id, switch_id, iface_urn, iface_href]
                info_insert(self._table_manager, 'ops_node_interface', 
                            node_iface_info)




    # update slice tables based on most recent snapshot
    def update_slice_tables(self):
        ts = int(time.time()*1000000)

        # Clear out old slice/user info
        self._table_manager.purge_old_tsdata('ops_slice', ts)
        self._table_manager.purge_old_tsdata('ops_user', ts)
        self._table_manager.purge_old_tsdata('ops_authority', ts)
        self.delete_all_entries_in_table('ops_slice_user')
        self.delete_all_entries_in_table('ops_authority_slice')

        user_urns = []
        authority_urns = []

        # Insert into ops_slice, ops_user and ops_slice_user tables 
        # for each active slice
        for object_urn, object_attributes in self._objects_by_urn.items():
            if object_attributes['__type__'] not in ['Slice']: continue

            user_urn = object_attributes['user_urn']
            slice_urn = object_attributes['slice_urn']
            slice_uuid = object_attributes['tenant_uuid']
            expires = object_attributes['expiration']

            authority_urn = getAuthorityURN(slice_urn, 'sa')
            authority_id = self.get_authority_id(authority_urn)
            authority_href = self.get_authority_href(authority_id)

            if authority_urn not in authority_urns:
                authority_urns.append(authority_urn)

            created = -1 # *** Can't get this

            # Insert into ops_slice table
            slice_id = self.get_slice_id(slice_urn)
            slice_href = self.get_slice_href(slice_id)
            slice_info = [self._slice_schema, slice_id, slice_href,
                          slice_urn, slice_uuid, ts, authority_urn, 
                          authority_href, created, expires]
            info_insert(self._table_manager, 'ops_slice', slice_info)

            # If user URN is present, link from slice to user
            if user_urn is not None:
                if user_urn not in user_urns: user_urns.append(user_urn)
                user_id = self.get_user_id(user_urn)
                user_href = self.get_user_href(user_id)
                role = None # *** Don't know what this is or how to get it
                slice_user_info = [user_id, slice_id, user_urn, role, user_href]
                info_insert(self._table_manager, 'ops_slice_user', slice_user_info)

            # Link from slice to authority
            auth_slice_info = [slice_id, authority_id, slice_urn, slice_href]
            info_insert(self._table_manager, 'ops_authority_slice', 
                        auth_slice_info)

        # Fill in users table
        for user_urn in user_urns:

            user_id = self.get_user_id(user_urn)
            user_href = self.get_user_href(user_id)

            authority_urn = getAuthorityURN(user_urn, 'ma')
            authority_id = self.get_authority_href(authority_urn)
            authority_href = self.get_authority_href(authority_id)

            if authority_urn not in authority_urns:
                authority_urns.append(authority_urn)

            full_name = None # *** Don't have this
            email = None # *** Don't have this

            user_info = [self._user_schema, user_id, user_href, user_urn, ts,
                         authority_urn, authority_href, full_name, email]
            info_insert(self._table_manager, 'ops_user', user_info)

        # Fill in authority table
        for authority_urn in authority_urns:
            authority_id = self.get_authority_id(authority_urn)
            authority_href = self.get_authority_href(authority_id)
            
            authority_info = [self._authority_schema, authority_id,
                              authority_href, authority_urn, ts]
            info_insert(self._table_manager, 'ops_authority', authority_info)
            

    # update sliver tables based on most recent snapshot
    def update_sliver_tables(self):
        ts = int(time.time()*1000000)

        # Clear out old sliver info:
        self._table_manager.purge_old_tsdata('ops_sliver', ts)
        # Clear out old sliver resource and aggregate sliver
        self.delete_all_entries_in_table('ops_sliver_resource')
        self.delete_all_entries_in_table('ops_aggregate_sliver')
            

        # Insert into ops_sliver_resource table and ops_aggregate_sliver table
        for object_urn, object_attributes in self._objects_by_urn.items():
            if object_attributes['__type__'] not in ['NetworkInterface', 'VirtualMachine']: continue
            slice_urn = object_attributes['slice_urn']
            sliver_id = flatten_urn(slice_urn) + "_" + object_attributes['name']
        
            # Insert into sliver tables
        for object_urn, object_attributes in self._objects_by_urn.items():
            if object_attributes['__type__'] not in ['NetworkInterface', 'VirtualMachine']: continue
            schema = self._sliver_schema
            slice_urn = object_attributes['slice_urn']
            sliver_id = flatten_urn(slice_urn) + "_" + object_attributes['name']
            sliver_href = self.get_sliver_href(sliver_id)
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
                node_href = self.get_sliver_resource_href(node_id)

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

    # Update aggregate measurement tables on most recent snapshot
    def update_aggregate_tables(self):
        ts = int(time.time()*1000000)

        num_vms_table = 'ops_aggregate_num_vms_allocated'

        # Clear out old node info
        self._table_manager.purge_old_tsdata(num_vms_table, ts)

        # Count number of VM's in current snapshot
        num_vms = 0
        for object_urn, object_attributes in self._objects_by_urn.items():
            if object_attributes['__type__'] == 'VirtualMachine': 
                num_vms = num_vms + 1
        
        # Write a record to the ops_aggregate_num_vms_allocated table
        num_vms_info = [self._aggregate_id, ts, num_vms]
        info_insert(self._table_manager, num_vms_table, num_vms_info)


    # Update data tables 
    # Remove old records
    # Grab new entries from hosts
    # and place in appropriate data tables
    def update_data_tables(self):

        ts = int(time.time()*1000000)
        window_threshold = ts - (self._window_duration_sec * 1000000)

        # Delete old records from data tables
        for command in self._node_commands + self._interface_commands:
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
                command = self._node_commands[i]
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

    def _compute_external_vlans(self):
        external_vlans = {}
        if 'stitching_info' in self._gram_config:
            stitching_info = self._gram_config['stitching_info']
            for ep in stitching_info['edge_points']:
                port = ep['port']
                vlans = ep['vlans']
                external_vlans[port] = parseVLANs(vlans)
        return external_vlans

    def delete_static_entries(self):
        self.delete_all_entries_in_table('ops_aggregate_resource')
        self.delete_all_entries_in_table('ops_link_interfacevlan')

    # Delete all entries in a given table
    def delete_all_entries_in_table(self, tablename):
        ids = self._table_manager.get_all_ids_from_table(tablename)
#        print "Deleting all entries in %s %s" % (tablename, ids)
        for id in ids:
            self._table_manager.delete_stmt(tablename, id)


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
                           'hosts', 'modules', 'node_commands', 
                           'interface_commands']
        missing_fields = []
        for field in required_fields:
            if field not in config: missing_fields.append(field)
        if len(missing_fields) > 0:
            sys.exit("Missing required fields in config: %s" % missing_fields)

        populator = OpsMonPopulator(config)
        populator.run()

# Parse a comma/hyphen set of sorted tags into a list of tags
def parseVLANs(vlan_spec):
    ranges = (x.split("-") for x in vlan_spec.split(","))
    return [i for r in ranges for i in range(int(r[0]), int(r[-1]) + 1)]

# Turn a urn into the urn of the authority that created it
def getAuthorityURN(urn, authority_type):
    pieces = urn.split(':')
    authority_id = pieces[2]
    return 'urn:publicid:%s+authority+%s' % (authority_id, authority_type)

if __name__ == "__main__":
    sys.exit(main())

