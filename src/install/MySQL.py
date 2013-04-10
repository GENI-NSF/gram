from GenericInstaller import GenericInstaller
from Configuration import Configuration



class MySQL(GenericInstaller):

    # Return a list of command strings for installing this component
    def installCommands(self, params):
        self.comment("*** MySQL Install ***")
        self.aptGet("mysql-server python-mysqldb")
        self.sed('s/127.0.0.1/0.0.0.0/g', '/etc/mysql/my.cnf')
        self.add("service mysql restart")
        sql_filename = '/tmp/commands.sql'
        self.writeToFile('CREATE DATABASE nova;', sql_filename)
        self.appendToFile('CREATE DATABASE glance;', sql_filename)
        self.appendToFile('CREATE DATABASE keystone;', sql_filename)
        self.appendToFile('CREATE DATABASE quantum;', sql_filename)
        self.generatePrivileges('nova', Configuration.ENV.NOVA_USER, \
                                    Configuration.ENV.NOVA_PASSWORD, params, \
                                    True, sql_filename)
        self.generatePrivileges('glance', Configuration.ENV.GLANCE_USER, \
                                    Configuration.ENV.GLANCE_PASSWORD, \
                                    params, False, sql_filename)
        self.generatePrivileges('keystone', Configuration.ENV.KEYSTONE_USER, \
                                    Configuration.ENV.KEYSTONE_PASSWORD, \
                                    params, False, sql_filename)
        self.generatePrivileges('quantum',  Configuration.ENV.QUANTUM_USER, \
                                    Configuration.ENV.QUANTUM_PASSWORD, \
                                    params, True, sql_filename)
        self.executeSQL(sql_filename, "$" + Configuration.ENV.MYSQL_PASSWORD)
        

    # return a list of command strings for uninstalling this component
    def uninstallCommands(self, params):
        self.comment("*** MySQL Uninstall ***")
        sql_filename = '/tmp/commands.sql'
        self.writeToFile('DROP DATABASE nova;', sql_filename)
        self.appendToFile('DROP DATABASE glance;', sql_filename)
        self.appendToFile('DROP DATABASE keystone;', sql_filename)
        self.appendToFile('DROP DATABASE quantum;', sql_filename)
        self.executeSQL(sql_filename, "$" + Configuration.ENV.MYSQL_PASSWORD)
        self.aptGet("mysql-server python-mysqldb", True)

    def generatePrivileges(self, db, user_var, user_pwd_var, params, \
                           compute_nodes, filename):
        self.generatePrivilegesForAddress(db, user_var, user_pwd_var, \
                                              'localhost', filename)
        if compute_nodes:
            nodes = params[Configuration.ENV.COMPUTE_HOSTS]
            for node in nodes:
                addr = nodes[node]
                self.generatePrivilegesForAddress(db, user_var, user_pwd_var, \
                                                      addr, filename)

    def generatePrivilegesForAddress(self, db, user_var, user_pwd_var, \
                                         address, filename):
        self.appendToFile("GRANT ALL PRIVILEGES ON " + db + ".* TO '" + 
                          "$" + user_var + "'@'" + address + 
                          "' IDENTIFIED BY '" + "$" + user_pwd_var + "';", 
                          filename)
    

