CC=gcc
CFLAGS=-I.

OBJ = gram_ssh_proxy.o

%.o: %.c $(CC) -c -o $@ $< $(CFLAGS)

gram_ssh_proxy: $(OBJ)
	gcc -o $@ $^ $(CFLAGS)
	chmod u+s gram_ssh_proxy

.PHONY: clean

clean:
	rm -f *.o core
