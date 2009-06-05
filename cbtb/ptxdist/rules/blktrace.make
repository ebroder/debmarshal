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
PACKAGES-$(PTXCONF_BLKTRACE) += blktrace

#
# Paths and names
#
BLKTRACE_VERSION	:= git-20070910192508
BLKTRACE		:= blktrace-$(BLKTRACE_VERSION)
BLKTRACE_SUFFIX		:= tar.gz
BLKTRACE_URL		:= http://brick.kernel.dk/snaps/$(BLKTRACE).$(BLKTRACE_SUFFIX)
BLKTRACE_SOURCE		:= $(SRCDIR)/$(BLKTRACE).$(BLKTRACE_SUFFIX)
BLKTRACE_DIR		:= $(BUILDDIR)/blktrace

# ----------------------------------------------------------------------------
# Get
# ----------------------------------------------------------------------------

blktrace_get: $(STATEDIR)/blktrace.get

$(STATEDIR)/blktrace.get: $(blktrace_get_deps_default)
	@$(call targetinfo, $@)
	@$(call touch, $@)

$(BLKTRACE_SOURCE):
	@$(call targetinfo, $@)
	@$(call get, BLKTRACE)

# ----------------------------------------------------------------------------
# Extract
# ----------------------------------------------------------------------------

blktrace_extract: $(STATEDIR)/blktrace.extract

$(STATEDIR)/blktrace.extract: $(blktrace_extract_deps_default)
	@$(call targetinfo, $@)
	@$(call clean, $(BLKTRACE_DIR))
	@$(call extract, BLKTRACE)
	@$(call patchin, BLKTRACE)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Prepare
# ----------------------------------------------------------------------------

blktrace_prepare: $(STATEDIR)/blktrace.prepare

BLKTRACE_PATH	:= PATH=$(CROSS_PATH)
BLKTRACE_ENV 	:= $(CROSS_ENV)

#
# autoconf
#
BLKTRACE_AUTOCONF := $(CROSS_AUTOCONF_USR)

$(STATEDIR)/blktrace.prepare: $(blktrace_prepare_deps_default)
	@$(call targetinfo, $@)
	@$(call clean, $(BLKTRACE_DIR)/config.cache)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Compile
# ----------------------------------------------------------------------------

blktrace_compile: $(STATEDIR)/blktrace.compile

$(STATEDIR)/blktrace.compile: $(blktrace_compile_deps_default)
	@$(call targetinfo, $@)
	cd $(BLKTRACE_DIR) && $(BLKTRACE_PATH) $(MAKE) $(PARALLELMFLAGS)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Install
# ----------------------------------------------------------------------------

blktrace_install: $(STATEDIR)/blktrace.install

$(STATEDIR)/blktrace.install: $(blktrace_install_deps_default)
	@$(call targetinfo, $@)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Target-Install
# ----------------------------------------------------------------------------

blktrace_targetinstall: $(STATEDIR)/blktrace.targetinstall

$(STATEDIR)/blktrace.targetinstall: $(blktrace_targetinstall_deps_default)
	@$(call targetinfo, $@)

	@$(call install_init, blktrace)
	@$(call install_fixup, blktrace,PACKAGE,blktrace)
	@$(call install_fixup, blktrace,PRIORITY,optional)
	@$(call install_fixup, blktrace,VERSION,$(BLKTRACE_VERSION))
	@$(call install_fixup, blktrace,SECTION,base)
	@$(call install_fixup, blktrace,AUTHOR,"Chuan-kai Lin <cklin\@google.com>")
	@$(call install_fixup, blktrace,DEPENDS,)
	@$(call install_fixup, blktrace,DESCRIPTION,missing)

	@$(call install_copy, blktrace, 0, 0, 0755, $(BLKTRACE_DIR)/blktrace, /usr/sbin/blktrace)

	@$(call install_finish, blktrace)

	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Clean
# ----------------------------------------------------------------------------

blktrace_clean:
	rm -rf $(STATEDIR)/blktrace.*
	rm -rf $(IMAGEDIR)/blktrace_*
	rm -rf $(BLKTRACE_DIR)

# vim: syntax=make
