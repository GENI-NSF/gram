CC=gcc
CFLAGS=-I.

INSTALL_DIR=/usr/local/bin

OBJ = gram_ssh_proxy.o

%.o: %.c $(CC) -c -o $@ $< $(CFLAGS)

gram_ssh_proxy: $(OBJ)
	gcc -o $@ $^ $(CFLAGS)
	cp -f $@ $(INSTALL_DIR)

.PHONY: clean

clean:
	rm -f *.o core
