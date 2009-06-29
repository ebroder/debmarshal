# Copyright 2009 Google Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.
#
# Author: Evan Broder <ebroder@google.com>

libexec_PROGRAMS = c/debmarshpriv

all-local: build-python
build-python: $(shell find . -name '*.py')
	$(PYTHON) setup.py build

check: check-python
check-python: check-python
	$(PYTHON) setup.py test

clean-local: clean-python
clean-python:
	$(PYTHON) setup.py clean -a

install-exec-local: install-python
install-python: build-python install-libexecPROGRAMS
	chmod u+s $(DESTDIR)$(libexecdir)/debmarshpriv

	if [ -n "$(DESTDIR)" ] ; then \
	    $(PYTHON) setup.py install --prefix $(prefix) --exec-prefix $(exec_prefix) --root $(DESTDIR) ; \
	else \
	    $(PYTHON) setup.py install --prefix $(prefix) --exec-prefix $(exec_prefix) ; \
	fi
