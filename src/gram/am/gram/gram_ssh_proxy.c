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
#include <sys/types.c>

#define IPTABLES_LOCATION_STR "/sbin/iptables"
#define PORT_TABLE_LOCATION "/tmp/gram-ssh-port-table.txt"
#define PORT_NUMBER_START 3000

#define MAX_PORT_TABLE_ENTRIES 500
#define MAX_ADDR_STRING_LENGTH 21
#define MAX_IPTABLES_CMD_STR_LEN 200

#define MODE_NONE 0
#define MODE_CREATE 1
#define MODE_DELETE 2

typedef char *entryType;

void add_proxy_cmd(char *addr, int portNumber)
{
  int cmdlen;
  char *cmd;

  cmd = (char *)malloc(sizeof(char) * MAX_IPTABLES_CMD_STR_LEN);

  setuid(0);
  if (fork() == 0)
  {
    memset(cmd, NULL, MAX_IPTABLES_CMD_STR_LEN);
    cmdlen = sprintf(cmd, "%s -t nat -I PREROUTING -p tcp --dport %d -j DNAT --to-destination %s:22 ",
		     IPTABLES_LOCATION_STR, portNumber, addr);  
    execl(cmd, NULL);

    memset(cmd, NULL, MAX_IPTABLES_CMD_STR_LEN);
    cmdlen = sprintf(cmd, "%s -I FORWARD -p tcp -s %s -j ACCEPT ",
		     IPTABLES_LOCATION_STR, addr);
    execl(cmd, NULL);

    memset(cmd, NULL, MAX_IPTABLES_CMD_STR_LEN);
    cmdlen = sprintf(cmd, "%s -t nat -I POSTROUTING -p tcp -s %s -j MASQUERADE ",
		     IPTABLES_LOCATION_STR, addr);  
    execl(cmd, NULL);
  }

  free(cmd);
}


void delete_proxy_cmd(char *addr, int portNumber)
{
  int cmdlen;
  char *cmd;

  cmd = (char *)malloc(sizeof(char) * MAX_IPTABLES_CMD_STR_LEN);

  setuid(0);
  if (fork() == 0)
  {
    memset(cmd, NULL, MAX_IPTABLES_CMD_STR_LEN);
    cmdlen = sprintf(cmd, "%s -t nat -D PREROUTING -p tcp --dport %d -j DNAT --to-destination %s:22 ",
		     IPTABLES_LOCATION_STR, portNumber, addr);  
    execl(cmd, NULL);

    memset(cmd, NULL, MAX_IPTABLES_CMD_STR_LEN);
    cmdlen = sprintf(cmd, "%s -D FORWARD -p tcp -s %s -j ACCEPT ",
		     IPTABLES_LOCATION_STR, addr);
    execl(cmd, NULL);

    memset(cmd, NULL, MAX_IPTABLES_CMD_STR_LEN);
    cmdlen = sprintf(cmd, "%s -D nat -I POSTROUTING -p tcp -s %s -j MASQUERADE ",
		     IPTABLES_LOCATION_STR, addr);  
    execl(cmd, NULL);
  }

  free(cmd);
}


int add_proxy(char *addr)
{
  FILE *pRead;
  FILE *pWrite;
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
  if (scanf(addr, "%d\.%d\.%d\.%d", addr0, addr1, addr2, addr3) != 4)
  {
    fprintf(stderr, "Bad address %s\n", addr);
    exit(EXIT_FAILURE);
  }

  /* Initialize state variables */
  duplicate = FALSE;
  portCounter = PORT_NUMBER_START;
  finalPortNumber = 0;
  entryIndex = 0;

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
      strlength = fscanf(pRead, "%d\.%d\.%d\d\t%d",  table0, table1, table2, table3, portNumber);
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
            sprintf(newEntry, "%d\.%d\.%d\.%d\t%d\n", table0, table1, table2, table3, portNumber);
            entries[entryIndex++] = newEntry;
            portCounter++;
          } else {
            newEntry = (entryType)malloc(sizeof(char) * MAX_ADDR_STRING_LENGTH);
            sprintf(newEntry, "%d\.%d\.%d\.%d\t%d\n", addr0, addr1, addr2, addr3, portCounter);
            entries[entryIndex++] = newEntry;
            finalPortNumber = portCounter;
          }
        } else {
          newEntry = (entryType)malloc(sizeof(char) * MAX_ADDR_STRING_LENGTH);
          sprintf(newEntry, "%d\.%d\.%d\.%d\t%d\n", table0, table1, table2, table3, portNumber);
          entries[entryIndex++] = newEntry;
        }
      } /* if strlength == 5 */
    } /* eof */

    /* close the read file */
    fclose(pRead);
  }

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
    fprintf(pWrite, "%s\t%d\n", addr, portCounter);
    fclose(pWrite);

    /* Return the port number */
    return portCounter;
  }

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
    fprintf(pWrite, entries[portCounter]);
    free(entries[portCounter]);
    portCounter++;
  }

  /* Close the file and return the port number */  
  fclose(pWrite);
  return finalPortNumber;
}


int delete_proxy(char *addr)
{
  FILE *pRead;
  FILE *pWrite;
  int strlength;
  int addr0;
  int addr1;
  int addr2;
  int addr3;
  int table0;
  int table1;
  int table2;
  int table3;
  int portCounter;
  entryType entries[MAX_PORT_TABLE_ENTRIES];
  entryType newEntry;
  int entryIndex;
  int finalPortNumber;

  /* Pasrse the address and check that it's valid */
  if (scanf(addr, "%d\.%d\.%d\.%d", addr0, addr1, addr2, addr3) != 4)
  {
    fprintf(stderr, "Bad address %s\n", addr);
    exit(EXIT_FAILURE);
  }

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
    strlength = fscanf(pRead, "%d\.%d\.%d\d\t%d",  table0, table1, table2, table3, portNumber);
    if (strlength == 5)
    {
      /* Break if the address is a duplication */
      if (table0 != addr0 || table1 != addr1 || table2 != addr2 || table3 != addr3)
      {
          newEntry = (entryType)malloc(sizeof(char) * MAX_ADDR_STRING_LENGTH);
          sprintf(newEntry, "%d\.%d\.%d\.%d\t%d\n", table0, table1, table2, table3, portNumber);
          entries[entryIndex++] = newEntry;
      } else {
	finalPortNumber = portNumber;
      }
    } /* if strlength == 5 */
  } /* eof */

  /* close the read file */
  fclose(pRead);

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
    fprintf(pWrite, entries[portCounter]);
    free(entries[portCounter]);
    portCounter++;
  }

  /* Close the file and return the port number */  
  fclose(pWrite);
  return finalPortNumber;
}


int main(int argc, char *argv[])
{
  int opt;
  char *addr;
  int mode;
  int portNumber;

  mode = MODE_NONE;
  addr = (char *)malloc(sizeof(char) * MAX_ADDR_STRING_LENGTH);
  while ((opt = getopt(argc, argv, "cd")) != -1)
  {
    switch (opt)
    {
    case 'c':
      strncpy(addr, optarg, MAX_ADDR_STRING_LENGTH);
      mode = MODE_CREATE;
      break;
    case 'd'
      mode = MODE_DELETE;
      strncpy(addr, optarg, MAX_ADDR_STRING_LENGTH);
      break;
    default:
      fprintf(stderr, "Usage %s [-c|-d] address\n", argv[0]);
      exit(EXIT_FAILURE);
    }
  }

  if (optind >= argc)
  {
    free(addr);
    fprintf(stderr, "Usage %s [-c|-d] address\n", argv[0]);
    exit(EXIT_FAILURE);
  }

  if (mode == MODE_NONE)
  {
    free(addr);
    fprintf(stderr, "Usage %s [-c|-d] address\n", argv[0]);
    exit(EXIT_FAILURE);      
  }

  if (mode == MODE_CREATE)
  {
    portNumber = add_proxy(addr);
    add_proxy_cmd(addr, portNumber);
  } else {
    portNumber = delete_proxy(addr);
    delete_proxy_cmd(addr, portNumber);
  }

  free(addr);
  exit(0);
}
