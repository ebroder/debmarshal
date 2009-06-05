# -*-makefile-*-
# $Id: template 6655 2007-01-02 12:55:21Z rsc $
#
# Copyright 2007 Google Inc.
# Author: cklin@google.com (Chuan-kai Lin)
#
# See CREDITS for details about who has contributed to this project.
#
# For further information about the PTXdist project and license conditions
# see the README file.
#

#
# We provide this package
#
PACKAGES-$(PTXCONF_TCT) += tct

#
# Paths and names
#
TCT_VERSION	:= 1.18
TCT		:= tct-$(TCT_VERSION)
TCT_SUFFIX		:= tar.gz
TCT_URL		:= http://www.porcupine.org/forensics/$(TCT).$(TCT_SUFFIX)
TCT_SOURCE		:= $(SRCDIR)/$(TCT).$(TCT_SUFFIX)
TCT_DIR		:= $(BUILDDIR)/$(TCT)

# ----------------------------------------------------------------------------
# Get
# ----------------------------------------------------------------------------

tct_get: $(STATEDIR)/tct.get

$(STATEDIR)/tct.get: $(tct_get_deps_default)
	@$(call targetinfo, $@)
	@$(call touch, $@)

$(TCT_SOURCE):
	@$(call targetinfo, $@)
	@$(call get, TCT)

# ----------------------------------------------------------------------------
# Extract
# ----------------------------------------------------------------------------

tct_extract: $(STATEDIR)/tct.extract

$(STATEDIR)/tct.extract: $(tct_extract_deps_default)
	@$(call targetinfo, $@)
	@$(call clean, $(TCT_DIR))
	@$(call extract, TCT)
	@$(call patchin, TCT)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Prepare
# ----------------------------------------------------------------------------

tct_prepare: $(STATEDIR)/tct.prepare

TCT_PATH	:= PATH=$(CROSS_PATH)
TCT_ENV 	:= $(CROSS_ENV)

#
# autoconf
#
TCT_AUTOCONF := $(CROSS_AUTOCONF_USR)

$(STATEDIR)/tct.prepare: $(tct_prepare_deps_default)
	@$(call targetinfo, $@)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Compile
# ----------------------------------------------------------------------------

tct_compile: $(STATEDIR)/tct.compile

$(STATEDIR)/tct.compile: $(tct_compile_deps_default)
	@$(call targetinfo, $@)
	cd $(TCT_DIR) && $(TCT_PATH) $(MAKE) -C src/misc $(PARALLELMFLAGS)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Install
# ----------------------------------------------------------------------------

tct_install: $(STATEDIR)/tct.install

$(STATEDIR)/tct.install: $(tct_install_deps_default)
	@$(call targetinfo, $@)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Target-Install
# ----------------------------------------------------------------------------

tct_targetinstall: $(STATEDIR)/tct.targetinstall

$(STATEDIR)/tct.targetinstall: $(tct_targetinstall_deps_default)
	@$(call targetinfo, $@)

	@$(call install_init, tct)
	@$(call install_fixup, tct,PACKAGE,tct)
	@$(call install_fixup, tct,PRIORITY,optional)
	@$(call install_fixup, tct,VERSION,$(TCT_VERSION))
	@$(call install_fixup, tct,SECTION,base)
	@$(call install_fixup, tct,AUTHOR,"Chuan-kai Lin <cklin\@google.com>")
	@$(call install_fixup, tct,DEPENDS,)
	@$(call install_fixup, tct,DESCRIPTION,missing)

ifdef PTXCONF_TCT_TIMEOUT
	@$(call install_copy, tct, 0, 0, 0755, $(TCT_DIR)/bin/timeout, /usr/bin/timeout)
endif

	@$(call install_finish, tct)

	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Clean
# ----------------------------------------------------------------------------

tct_clean:
	rm -rf $(STATEDIR)/tct.*
	rm -rf $(IMAGEDIR)/tct_*
	rm -rf $(TCT_DIR)

# vim: syntax=make
