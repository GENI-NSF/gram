/*#----------------------------------------------------------------------
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
*/

#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <errno.h>
#include <fcntl.h>

#define IPTABLES_LOCATION_STR "/sbin/iptables"
#define PORT_TABLE_LOCATION "/etc/gram/gram-ssh-port-table.txt"
#define PORT_TABLE_LOCKFILE "/etc/gram/gram-ssh-port-table.lock"
#define PORT_NUMBER_START 3100
#define PORT_MIN_NUMBER 1024

#define MAX_PORT_TABLE_ENTRIES 1000
#define MAX_ADDR_STRING_LENGTH 21
#define MAX_PORT_STRING_LENGTH 6
#define MAX_IPTABLES_CMD_STR_LEN 200
#define MAX_NAMESPACE_STRING_LENGTH 100

#define ENABLE_FCNTL

#define MODE_NONE 0
#define MODE_CREATE 1
#define MODE_DELETE 2
#define MODE_CLEAR  3
#define MODE_LIST 4

#define TRUE 1
#define FALSE 0

#define USAGE_STRING "Usage %s -m [{c|d} -a address | x]\n"

typedef char *entryType;

void add_proxy_cmd(char *addr, int portNumber, char *namespace)
{
  int cmdlen;
  char *cmd;
  pid_t pid;

  cmd = (char *)malloc(sizeof(char) * MAX_IPTABLES_CMD_STR_LEN);

  /* NOTE: The "add" iptable commands must use the insert "-I" flag instead of the append "-A"
     flag because openstack also manipulates the iptables, and the SSH proxy rules must come before
     the openstack rules- if the SSH proxy rules come after the openstack NAT rules, then the proxy
     will not work */
  memset(cmd, (int)'\0', MAX_IPTABLES_CMD_STR_LEN);
  cmdlen = sprintf(cmd, "ip netns exec %s %s -t nat -I PREROUTING -p tcp --dport %d -j DNAT --to-destination %s:22 ",
                   namespace, IPTABLES_LOCATION_STR, portNumber, addr);
  fprintf(stdout, "%s\n", cmd);
  system(cmd);

  memset(cmd, (int)'\0', MAX_IPTABLES_CMD_STR_LEN);
  cmdlen = sprintf(cmd, "ip netns exec %s %s -I FORWARD -p tcp -s %s -j ACCEPT ",
                   namespace, IPTABLES_LOCATION_STR, addr);
  fprintf(stdout, "%s\n", cmd);
  system(cmd);

  memset(cmd, (int)'\0', MAX_IPTABLES_CMD_STR_LEN);
  cmdlen = sprintf(cmd, "ip netns exec %s %s -t nat -I POSTROUTING -p tcp -s %s -j MASQUERADE ",
                   namespace, IPTABLES_LOCATION_STR, addr);  
  fprintf(stdout, "%s\n", cmd);
  system(cmd);

  free(cmd);
}


void delete_proxy_cmd(char *addr, int portNumber, char *namespace)
{
  int cmdlen;
  char *cmd;

  cmd = (char *)malloc(sizeof(char) * MAX_IPTABLES_CMD_STR_LEN);

  memset(cmd, (int)'\0', MAX_IPTABLES_CMD_STR_LEN);
  cmdlen = sprintf(cmd, "ip netns exec %s %s -t nat -D PREROUTING -p tcp --dport %d -j DNAT --to-destination %s:22 ",
                   namespace, IPTABLES_LOCATION_STR, portNumber, addr);  
  fprintf(stdout, "%s\n", cmd);
  system(cmd);

  memset(cmd, (int)'\0', MAX_IPTABLES_CMD_STR_LEN);
  cmdlen = sprintf(cmd, "ip netns exec %s %s -D FORWARD -p tcp -s %s -j ACCEPT ",
                   namespace, IPTABLES_LOCATION_STR, addr);
  fprintf(stdout, "%s\n", cmd);
  system(cmd);

  memset(cmd, (int)'\0', MAX_IPTABLES_CMD_STR_LEN);
  cmdlen = sprintf(cmd, "ip netns exec %s %s -t nat -D POSTROUTING -p tcp -s %s -j MASQUERADE ",
                   namespace, IPTABLES_LOCATION_STR, addr);  
  fprintf(stdout, "%s\n", cmd);
  system(cmd);

  free(cmd);
}


void delete_table_cmd()
{
  int cmdlen;
  char *cmd;

  cmd = (char *)malloc(sizeof(char) * MAX_IPTABLES_CMD_STR_LEN);

  memset(cmd, (int)'\0', MAX_IPTABLES_CMD_STR_LEN);
  sprintf(cmd, "rm -f %s ", PORT_TABLE_LOCATION);  
  fprintf(stdout, "%s\n", cmd);
  system(cmd);

  free(cmd);
}


int acquire_read_lock()
{
  struct flock filelock;
  int lockfile;

  filelock.l_type = F_RDLCK;
  filelock.l_whence = SEEK_SET;
  filelock.l_start = 0;
  filelock.l_len = 0;
  filelock.l_pid = getpid();

  lockfile = open(PORT_TABLE_LOCKFILE, O_RDONLY | O_CREAT, S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH);
  if (lockfile == -1)
  {
    fprintf(stderr, "Unable to open read file lock for %s\n", PORT_TABLE_LOCKFILE);
    exit(EXIT_FAILURE);
  }

  if (fcntl(lockfile, F_SETLKW, &filelock) == -1)
  {
    fprintf(stderr, "Unable to acquire read file lock for %s\n", PORT_TABLE_LOCKFILE);
    exit(EXIT_FAILURE);
  }

  return lockfile;
}


int acquire_write_lock()
{
  int lockfile;
  struct flock filelock;

  filelock.l_type = F_WRLCK;
  filelock.l_whence = SEEK_SET;
  filelock.l_start = 0;
  filelock.l_len = 0;
  filelock.l_pid = getpid();

  lockfile = open(PORT_TABLE_LOCKFILE, O_WRONLY | O_CREAT, S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH);
  if (lockfile == -1)
  {
    fprintf(stderr, "Unable to open write file lock for %s\n", PORT_TABLE_LOCKFILE);
    exit(EXIT_FAILURE);
  }

  if (fcntl(lockfile, F_SETLKW, &filelock) == -1)
  {
    fprintf(stderr, "Unable to acquire write file lock for %s\n", PORT_TABLE_LOCKFILE);
    exit(EXIT_FAILURE);
  }
 
  return lockfile;
}


void release_lock(int lockfile)
{
  struct flock filelock;

  filelock.l_type = F_UNLCK;
  filelock.l_whence = SEEK_SET;
  filelock.l_start = 0;
  filelock.l_len = 0;
  filelock.l_pid = getpid();
  
  if (fcntl(lockfile, F_SETLK, &filelock) == -1)
  {
    fprintf(stderr, "Error trying to release file lock\n");
    exit(EXIT_FAILURE);
  }

  close(lockfile);
}


void parse_address(char *addr, int *addr0, int *addr1, int *addr2, int *addr3)
{
  int strlength;
  char *addrcpy;
  char *token;

  /* Pasrse the address and check that it's valid */
  strlength = 0;
  addrcpy = (char*)malloc(sizeof(char) * strlen(addr) + 1);
  strcpy(addrcpy, addr);
  token = strtok(addrcpy, ".");
  if (token != NULL)
  {
    *addr0 = atoi(token);
    strlength++;
    token = strtok(NULL, ".");
    if (token != NULL)
    {
      strlength++;
      *addr1 = atoi(token);
      token = strtok(NULL, ".");
      if (token != NULL)
      {
        strlength++;
        *addr2 = atoi(token);
        token = strtok(NULL, ".");
        if (token != NULL)
	{
          strlength++;
	  *addr3 = atoi(token);
	}
      }
    }
  }

  free(addrcpy);
  if (strlength != 4)
  {
    fprintf(stderr, "Bad address %s\n", addr);
    exit(EXIT_FAILURE);
  }  
}


int add_proxy(char *addr)
{
  FILE *pRead;
  FILE *pWrite;
  int lockfile;
  int strlength;
  int addr0;
  int addr1;
  int addr2;
  int addr3;
  int table0;
  int table1;
  int table2;
  int table3;
  int portNumber;
  int portCounter;
  int finalPortNumber;
  int duplicate;
  entryType entries[MAX_PORT_TABLE_ENTRIES];
  entryType newEntry;
  int entryIndex;

  /* Pasrse the address and check that it's valid */
  parse_address(addr, &addr0, &addr1, &addr2, &addr3);
  /*fprintf(stdout, "Address: %d.%d.%d.%d\n", addr0, addr1, addr2, addr3);*/

  /* Initialize state variables */
  duplicate = FALSE;
  portCounter = PORT_NUMBER_START;
  finalPortNumber = 0;
  entryIndex = 0;

#ifdef ENABLE_FCNTL
  /* Acquire the lock for the port address table file */
  lockfile = acquire_read_lock();
#endif

  /* Open the port table for reading */
  pRead = fopen(PORT_TABLE_LOCATION, "r");
  if (pRead != NULL)
  {
    /* Iterate over the port table
       Read each line entry and store contents
       Quit if address is a duplicate
       If port number available, then assing address to port and insert it into the sorted table
    */
    while (!feof(pRead))
    {
      /* Read the line */
      strlength = fscanf(pRead, "%d.%d.%d.%d\t%d",  &table0, &table1, &table2, &table3, &portNumber);
      if (strlength == 5)
      {
        /* Break if the address is a duplication */
        if (table0 == addr0 && table1 == addr1 && table2 == addr2 && table3 == addr3)
        {
          duplicate = TRUE;
          break;
        }

        /* Update the table as necessary */
        if (finalPortNumber == 0)
        {
          /* If port is free then assign the address to it, otherwise copy the port entry back into the table */
          if (portCounter == portNumber)
          {
            newEntry = (entryType)malloc(sizeof(char) * MAX_ADDR_STRING_LENGTH);
            sprintf(newEntry, "%d.%d.%d.%d\t%d\n", table0, table1, table2, table3, portNumber);
            entries[entryIndex++] = newEntry;
            portCounter++;
          } else {
            newEntry = (entryType)malloc(sizeof(char) * MAX_ADDR_STRING_LENGTH);
            sprintf(newEntry, "%d.%d.%d.%d\t%d\n", addr0, addr1, addr2, addr3, portCounter);
            entries[entryIndex++] = newEntry;
            finalPortNumber = portCounter;
          }
        } else {
          newEntry = (entryType)malloc(sizeof(char) * MAX_ADDR_STRING_LENGTH);
          sprintf(newEntry, "%d.%d.%d.%d\t%d\n", table0, table1, table2, table3, portNumber);
          entries[entryIndex++] = newEntry;
        }
      } /* if strlength == 5 */
    } /* eof */

    /* close the read file */
    fclose(pRead);
  }

#ifdef ENABLE_FCNTL
  /* Release the port table file lock */
  release_lock(lockfile);
#endif

  /* Exit if duplicate */
  if (duplicate)
  {
    /* Clean up memory before exiting */
    while (entryIndex > 0)
    {
      free(entries[entryIndex - 1]);
      entryIndex--;
    }

    fprintf(stderr, "Duplicate address %s in port table\n", addr);
    exit(EXIT_FAILURE);
  }

#ifdef ENABLE_FCNTL
  /* Acquire write lock on port address file */
  lockfile = acquire_write_lock();
#endif

  /* Append port table if port number at end (or its port table is new) */
  if (finalPortNumber == 0)
  {
    /* Clean up memory first */
    while (entryIndex > 0)
    {
      free(entries[entryIndex - 1]);
      entryIndex--;
    }

    /* Open the file for writing */
    pWrite = fopen(PORT_TABLE_LOCATION, "a");
    if (pWrite == NULL)
    {
      fprintf(stderr, "Unable to open port address table %s for appending\n", PORT_TABLE_LOCATION);
      exit(EXIT_FAILURE);
    }

    /* Write the new entry and close the file */
    /*fprintf(stdout, "Appending file %s\n", PORT_TABLE_LOCATION);*/
    fprintf(pWrite, "%s\t%d\n", addr, portCounter);
    /*fprintf(stdout, "%s\t%d\n", addr, portCounter);*/
    fclose(pWrite);

    /* Return the port number */
    finalPortNumber = portCounter;
  } else {
    /* Otherwise rewrite the port address table file with the updated entries */
    pWrite = fopen(PORT_TABLE_LOCATION, "w");
    if (pWrite == NULL)
    {
      fprintf(stderr, "Unable to open port address table %s for writing\n", PORT_TABLE_LOCATION);
      exit(EXIT_FAILURE);
    }

    /* Iterate through the updated entries and write the contents to file */
    portCounter = 0;
    while (portCounter < entryIndex)
    {
      fprintf(pWrite, "%s", entries[portCounter]);
      free(entries[portCounter]);
      portCounter++;
    }

    /* Close the file and return the port number */  
    fclose(pWrite);
  }

#ifdef ENABLE_FCNTL
  /* Give up file lock */
  release_lock(lockfile);
#endif

  return finalPortNumber;
}


int add_proxy_with_port(char *addr, char *prt)
{
  FILE *pRead;
  int lockfile;
  int strlength;
  int addr0;
  int addr1;
  int addr2;
  int addr3;
  int table0;
  int table1;
  int table2;
  int table3;
  int portNumber;
  int finalPortNumber;
  int duplicate;

  /* Pasrse the address and check that it's valid */
  parse_address(addr, &addr0, &addr1, &addr2, &addr3);
  /*fprintf(stdout, "Address: %d.%d.%d.%d\n", addr0, addr1, addr2, addr3);*/

  /* Initialize state variables */
  duplicate = FALSE;
  finalPortNumber = atoi(prt);

  if (finalPortNumber < PORT_MIN_NUMBER)
  {
    fprintf(stderr, "Bad port number: %s\n", prt);
    exit(EXIT_FAILURE);
  }

#ifdef ENABLE_FCNTL
  /* Acquire the lock for the port address table file */
  lockfile = acquire_read_lock();
#endif

  /* Open the port table for reading */
  pRead = fopen(PORT_TABLE_LOCATION, "r");
  if (pRead != NULL)
  {
    /* Iterate over the port table
       Read each line entry and store contents
       Determine if given address and port are already in the table
    */
    while (!feof(pRead))
    {
      /* Read the line */
      strlength = fscanf(pRead, "%d.%d.%d.%d\t%d",  &table0, &table1, &table2, &table3, &portNumber);
      if (strlength == 5)
      {
        /* Break if the address is a duplication */
        if (table0 == addr0 && table1 == addr1 && table2 == addr2 && table3 == addr3 && portNumber == finalPortNumber)
        {
          duplicate = TRUE;
          break;
        }
      } /* if strlength == 5 */
    } /* eof */

    /* close the read file */
    fclose(pRead);
  }

#ifdef ENABLE_FCNTL
  /* Release the port table file lock */
  release_lock(lockfile);
#endif

  /* Exit if duplicate */
  if (!duplicate)
  {
    fprintf(stderr, "Address %s and port number %s not found in port table\n", addr, prt);
    exit(EXIT_FAILURE);
  }

  return finalPortNumber;
}


int delete_proxy(char *addr)
{
  FILE *pRead;
  FILE *pWrite;
  int lockfile;
  int strlength;
  int addr0;
  int addr1;
  int addr2;
  int addr3;
  int table0;
  int table1;
  int table2;
  int table3;
  int portNumber;
  int portCounter;
  entryType entries[MAX_PORT_TABLE_ENTRIES];
  entryType newEntry;
  int entryIndex;
  int finalPortNumber;

  /* Pasrse the address and check that it's valid */
  parse_address(addr, &addr0, &addr1, &addr2, &addr3);
  /*fprintf(stdout, "Address: %d.%d.%d.%d\n", addr0, addr1, addr2, addr3);*/

#ifdef ENABLE_FCNTL
  /* Secure the read lock on the port address file */
  lockfile = acquire_read_lock();
#endif

  /* Open the port table for reading */
  entryIndex = 0;
  pRead = fopen(PORT_TABLE_LOCATION, "r");
  if (pRead == NULL)
  {
      fprintf(stderr, "Unable to open port address table %s for reading\n", PORT_TABLE_LOCATION);
      exit(EXIT_FAILURE);
  }

  /* Iterate over the port table
     Read each line entry and store contents
     Add entry to list of outgoing lines if address does not match
  */
  finalPortNumber = 0;
  while (!feof(pRead))
  {
    /* Read the line */
    strlength = fscanf(pRead, "%d.%d.%d.%d\t%d",  &table0, &table1, &table2, &table3, &portNumber);
    if (strlength == 5)
    {
      /* Break if the address is a duplication */
      if (table0 != addr0 || table1 != addr1 || table2 != addr2 || table3 != addr3)
      {
          newEntry = (entryType)malloc(sizeof(char) * MAX_ADDR_STRING_LENGTH);
          sprintf(newEntry, "%d.%d.%d.%d\t%d\n", table0, table1, table2, table3, portNumber);
          entries[entryIndex++] = newEntry;
      } else {
	finalPortNumber = portNumber;
      }
    } /* if strlength == 5 */
  } /* eof */

  /* close the read file */
  fclose(pRead);

#ifdef ENABLE_FCNTL
  /* Release the read file lock */
  release_lock(lockfile);
#endif

  /* Verify that the address was found */
  if (finalPortNumber == 0)
  {
    /* Clean up memory */
    while (entryIndex > 0)
    {
      free(entries[entryIndex - 1]);
      entryIndex--;
    }

    fprintf(stderr, "Address %s not present in the port address table\n", addr);
    exit(EXIT_FAILURE);
  }

#ifdef ENABLE_FCNTL
  /* Secure the write lock on the port address file */
  lockfile = acquire_write_lock();
#endif

  /* Otherwise rewrite the port address table file with the updated entries */
  pWrite = fopen(PORT_TABLE_LOCATION, "w");
  if (pWrite == NULL)
  {
    fprintf(stderr, "Unable to open port address table %s for writing\n", PORT_TABLE_LOCATION);
    exit(EXIT_FAILURE);
  }

  /* Iterate through the updated entries and write the contents to file */
  portCounter = 0;
  while (portCounter < entryIndex)
  {
    fprintf(pWrite, "%s", entries[portCounter]);
    free(entries[portCounter]);
    portCounter++;
  }

  /* Close the file and return the port number */  
  fclose(pWrite);

#ifdef ENABLE_FCNTL
  /* Release the port address file lock */
  release_lock(lockfile);
#endif

  return finalPortNumber;
}


int clear_all_proxies(char *namespace)
{
  FILE *pRead;
  int lockfile;
  int strlength;
  int addr0;
  int addr1;
  int addr2;
  int addr3;
  int portNumber;
  char *addr;

#ifdef ENABLE_FCNTL
  /* Secure the read lock on the port address file */
  lockfile = acquire_write_lock();
#endif

  /* Open the port table for reading */
  pRead = fopen(PORT_TABLE_LOCATION, "r");
  if (pRead == NULL)
  {
      fprintf(stderr, "Unable to open port address table %s for reading\n", PORT_TABLE_LOCATION);
      exit(EXIT_FAILURE);
  }

  /* Iterate over the port table
     Read each line entry and store contents
     Invoke delete commands for each valid entry
  */
  while (!feof(pRead))
  {
    /* Read the line */
    strlength = fscanf(pRead, "%d.%d.%d.%d\t%d",  &addr0, &addr1, &addr2, &addr3, &portNumber);
    if (strlength == 5)
    {
      addr = (char *)malloc(sizeof(char) * MAX_ADDR_STRING_LENGTH);
      memset(addr, (int)'\0', MAX_ADDR_STRING_LENGTH);
      sprintf(addr, "%d.%d.%d.%d", addr0, addr1, addr2, addr3);
      delete_proxy_cmd(addr, portNumber, namespace);
      free(addr);
    } /* if strlength == 5 */
  } /* eof */

  /* close the read file */
  fclose(pRead);

  delete_table_cmd();

#ifdef ENABLE_FCNTL
  /* Release the read file lock */
  release_lock(lockfile);
#endif

  return FALSE;
}


int main(int argc, char *argv[])
{
  int opt;
  char *addr;
  char *prt;
  char *namespace;
  int mode;
  int portNumber;
  int addr_not_found = TRUE;
  int port_not_found = TRUE;
  int namespace_not_found = TRUE;

  mode = MODE_NONE;
  addr = (char *)malloc(sizeof(char) * MAX_ADDR_STRING_LENGTH);
  prt = (char *)malloc(sizeof(char) * MAX_PORT_STRING_LENGTH);
  namespace = (char *)malloc(sizeof(char) * MAX_NAMESPACE_STRING_LENGTH);
  while ((opt = getopt(argc, argv, "m:a:p:n:")) != -1)
  {
    /*fprintf(stdout, "Option %c\n", opt); */
    switch (opt)
    {
    case 'm':
      if (*optarg == 'c' || *optarg == 'C')
      {
        /*fprintf(stdout, "Mode Create\n");*/
        mode = MODE_CREATE;
      } else if (*optarg == 'd' || *optarg == 'D') {
        /*fprintf(stdout, "Mode Delete\n");*/
        mode = MODE_DELETE;
      } else if (*optarg == 'x' || *optarg == 'X') {
        mode = MODE_CLEAR;
      } else if (*optarg == 'l' || *optarg == 'L') {
        mode = MODE_LIST;
      } else {
        fprintf(stderr, USAGE_STRING, argv[0]);
        exit(EXIT_FAILURE);
      }
      break;
    case 'p':
      strncpy(prt, optarg, MAX_PORT_STRING_LENGTH);
      port_not_found = FALSE;
      break;
    case 'a':
      /*fprintf(stdout, "Address %s\n", (char*)optarg);*/
      strncpy(addr, optarg, MAX_ADDR_STRING_LENGTH);
      addr_not_found = FALSE;
      break;
    case 'n':
      strncpy(namespace, optarg, MAX_NAMESPACE_STRING_LENGTH);
      namespace_not_found = FALSE;      
      break; 
    default:
      fprintf(stderr, USAGE_STRING, argv[0]);
      exit(EXIT_FAILURE);
    }
  }

  if (mode == MODE_NONE || (mode != MODE_LIST && mode != MODE_CLEAR && addr_not_found))
  {
    free(addr);
    fprintf(stderr, USAGE_STRING, argv[0]);
    exit(EXIT_FAILURE);      
  }

  if (mode == MODE_LIST)
  {
    int cmdlen;
    char *cmd;
    cmd = (char *)malloc(sizeof(char) * MAX_IPTABLES_CMD_STR_LEN);
    memset(cmd, (int)'\0', MAX_IPTABLES_CMD_STR_LEN);
    cmdlen = sprintf(cmd, "ip netns exec %s %s -L -t nat --line-numbers",
                   namespace, IPTABLES_LOCATION_STR);
    fprintf(stdout, "%s\n", cmd);
    system(cmd);

  } else if (mode == MODE_CREATE){
    if (port_not_found)
    {
      fprintf(stdout, "Creating SSH Proxy for address %s\n", addr);
      portNumber = add_proxy(addr);
      fprintf(stdout, "Assigned port number %d\n", portNumber);
    } else {
      fprintf(stdout, "Creating SSH Proxy for address %s and port %s\n", addr, prt);
      portNumber = add_proxy_with_port(addr, prt);
      fprintf(stdout, "Done.\n");
   }

    add_proxy_cmd(addr, portNumber,namespace);

  } else if (mode == MODE_DELETE) {
    /* RRH - moved to !port_not_found - don't know why it was port_not_found only  then reverted because it really should have worked - still looking*/
    if (port_not_found)
    {
      fprintf(stdout, "Deleting SSH Proxy for address %s\n", addr);
      portNumber = delete_proxy(addr);
      fprintf(stdout, "Assigned port number %d\n", portNumber);
    } else {
      portNumber = atoi(prt);
    }

    delete_proxy_cmd(addr, portNumber,namespace);
  } else {
    fprintf(stdout, "Clearing all SSH Proxy addresses %s\n", addr);
    clear_all_proxies(namespace);
  }

  free(addr);
  exit(0);
}
