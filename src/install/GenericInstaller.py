# Generic installer for a class of OpenStack install/uninstall commands
# Each installer is responsible for returning a list of command strings
class GenericInstaller:

    def __init__(self):
        self.clear()

    def getCommands(self) : 
        return self._commands

    def clear(self): 
        self._commands = []
    
    # Return a list of command strings for installing this component
    def installCommands(self, params):
        pass

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self, params):
        pass

    def add(self,  command):
        self._commands.append(command)

    # Helper routines
    def comment(self, comment):
        self.add("# " + comment)

    def writeToFile(self, command, filename):
        cmd = "echo " + '"' + command + '"' + " > " + filename
        self.add(cmd)

    def appendToFile(self, command, filename):
        cmd = "echo " + '"' + command + '"' + " >> " + filename
        self.add(cmd)

    def executeSQL(self, filename, mysql_password):
        cmd =  "cat " + filename + " | mysql -u root -p" + mysql_password
        self.add(cmd)

    def aptGet(self, modules, uninstall=False):
        apt_command = "install"
        if(uninstall): apt_command = "remove"
        cmd = "apt-get " + apt_command + " -y " + modules
        self.add(cmd)

    def sed(self, regexp, file):
        sed_command = "sed -i '" + regexp + "' " + file
        self.add(sed_command)


