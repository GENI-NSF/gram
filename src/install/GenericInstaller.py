# Generic installer for a class of OpenStack install/uninstall commands
# Each installer is responsible for returning a list of command strings
class GenericInstaller:

    def __init__(self):
        self.clear()

    # Get all accumulated commands
    def getCommands(self) : 
        return self._commands

    # Clear currently accumulated set of commands
    def clear(self): 
        self._commands = []
    
    # Return a list of command strings for installing this component
    def installCommands(self, params):
        pass

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self, params):
        pass

    # Add a command to list of commands being accumulated
    def add(self,  command):
        self._commands.append(command)

    # Helper routines

    # Add a comment to a script file
    def comment(self, comment):
        self.add("# " + comment)


    # Write a line to file (wiping out any previous contents)
    def writeToFile(self, command, filename):
        cmd = "echo " + '"' + command + '"' + " > " + filename
        self.add(cmd)

    # Append line to given file
    def appendToFile(self, command, filename):
        cmd = "echo '" + command + "'" + " >> " + filename
        self.add(cmd)

    # Execute a set of SQL command from a file into MYSQL database (as root)
    def executeSQL(self, filename, mysql_password):
        cmd =  "cat " + filename + " | mysql -u root -p" + mysql_password
        self.add(cmd)

    # Perform apt-get command (install or uninstall)
    def aptGet(self, modules, uninstall=False, force=False):
        apt_command = "install"
        if(uninstall): apt_command = "remove"
        options = " -y "
        if force:
            options = options + " --force-yes "
        cmd = "apt-get " + apt_command +options + modules
        self.add(cmd)

    # Run an invasive (editing file inline) SED command on file
    def sed(self, regexp, file):
        sed_command = "sed -i " + "\""+ regexp + "\"" + " " + file
        self.add(sed_command)


    # Backup a file before changing it
    def backup(self, directory, backup_directory, file):
        self.add("cp " + directory + "/" + file + " " + backup_directory)

    # Restore a file back to original state
    def restore(self, directory, backup_directory, file):
        self.add("cp " + backup_directory + "/" + file + " " + directory)
