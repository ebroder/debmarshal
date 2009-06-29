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
