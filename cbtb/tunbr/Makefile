CFLAGS=-W -O2 -g `./tunbr-config`
BINDIR=usr/local/bin

all: tunbr

install: tunbr
	cp tunbr $(DESTDIR)/$(BINDIR)/
	chown root $(DESTDIR)/$(BINDIR)/tunbr
	chmod 4755 $(DESTDIR)/$(BINDIR)/tunbr
