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
        self.generatePrivileges('nova', config.nova_user, \
                                    config.nova_password, 
                                    True, sql_filename)
        self.generatePrivileges('glance', config.glance_user, \
                                    config.glance_password, \
                                    False, sql_filename)
        self.generatePrivileges('keystone', config.keystone_user,
                                    config.keystone_password, \
                                    False, sql_filename)
        self.generatePrivileges('quantum',  config.quantum_user, \
                                    config.quantum_password, \
                                    True, sql_filename)
        self.executeSQL(sql_filename, config.mysql_password)
        

    # return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        self.comment("*** MySQL Uninstall ***")
        sql_filename = '/tmp/commands.sql'
        self.writeToFile('DROP DATABASE nova;', sql_filename)
        self.appendToFile('DROP DATABASE glance;', sql_filename)
        self.appendToFile('DROP DATABASE keystone;', sql_filename)
        self.appendToFile('DROP DATABASE quantum;', sql_filename)
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
    

