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

from GenericInstaller import GenericInstaller
from gram.am.gram import config

class MySQL(GenericInstaller):

    # Return a list of command strings for installing this component
    def installCommands(self):
        self.comment("*** MySQL Install ***")
        self.sed('s/127.0.0.1/0.0.0.0/g', '/etc/mysql/my.cnf')
        self.add("service mysql restart")
        sql_filename = '/tmp/commands.sql'
        self.writeToFile('CREATE DATABASE nova;', sql_filename)
        self.appendToFile('CREATE DATABASE glance;', sql_filename)
        self.appendToFile('CREATE DATABASE keystone;', sql_filename)
        self.appendToFile('CREATE DATABASE quantum;', sql_filename)
        self.appendToFile('CREATE DATABASE monitoring;', sql_filename)
        self.generatePrivileges('nova', config.nova_user, \
                                    config.nova_password, 
                                    True, sql_filename)
        self.generatePrivileges('glance', config.glance_user, \
                                    config.glance_password, \
                                    False, sql_filename)
        self.generatePrivileges('keystone', config.keystone_user,
                                    config.keystone_password, \
                                    False, sql_filename)
        self.generatePrivileges('quantum',  config.network_user, \
                                    config.network_password, \
                                    True, sql_filename)
        self.generatePrivileges('monitoring',  config.network_user, \
                                    config.network_password, \
                                    True, sql_filename)
        self.executeSQL(sql_filename, config.mysql_password)
        #Not really sure this should happen here - need to go to the directory - paths are not absolute
        #Leaving for reference, but should be done by hand for now - RRH 5/13/2014
        #self.comment("Create monitoring schema - needs to be done after DB creation")
        #self.add('cd /home/gram/ops-monitoring/local/unit-tests')
        #self.add('python local_table_reset.py')
        

    # return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        self.comment("*** MySQL Uninstall ***")
        sql_filename = '/tmp/commands.sql'
        self.writeToFile('DROP DATABASE nova;', sql_filename)
        self.appendToFile('DROP DATABASE glance;', sql_filename)
        self.appendToFile('DROP DATABASE keystone;', sql_filename)
        self.appendToFile('DROP DATABASE quantum;', sql_filename)
        self.appendToFile('DROP DATABASE monitoring;', sql_filename)
        self.executeSQL(sql_filename, config.mysql_password)

    def generatePrivileges(self, db, user_name, user_pwd, \
                           compute_nodes, filename):
        self.generatePrivilegesForAddress(db, user_name, user_pwd, 'localhost', filename)
        self.generatePrivilegesForAddress(db, user_name, user_pwd, config.control_address, filename)
        if compute_nodes:
            nodes = config.compute_hosts
            for node in nodes:
                addr = nodes[node]
                self.generatePrivilegesForAddress(db, user_name, user_pwd, addr, filename)

    def generatePrivilegesForAddress(self, db, user_name, user_pwd, \
                                         address, filename):
        self.appendToFile("GRANT ALL PRIVILEGES ON " + db + ".* TO " + '"' +
                          user_name + '"' + "@" + '"' + address + '"' + 
                          " IDENTIFIED BY " + '"' + user_pwd + '"' + ";", 
                          filename)
    

