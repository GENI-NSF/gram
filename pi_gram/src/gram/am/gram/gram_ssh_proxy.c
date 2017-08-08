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
  fprintf(stdout, "%d\n", portNumber);
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



int main(int argc, char *argv[])
{
  int opt;
  char *addr;
  char *prt;
  char *namespace;
  int mode;
  int portNumber;
  int addr_not_found = TRUE;
  int namespace_not_found = TRUE;

  fprintf(stdout, "in main");

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
    portNumber = atoi(prt);
    add_proxy_cmd(addr, portNumber,namespace);

  } else if (mode == MODE_DELETE) {
    portNumber = atoi(prt);
    delete_proxy_cmd(addr, portNumber,namespace);
  } else {
    fprintf(stdout, "Unknown command %s\n", addr);
  }

  free(addr);
  exit(0);
}
