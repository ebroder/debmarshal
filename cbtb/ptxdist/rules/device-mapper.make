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
PACKAGES-$(PTXCONF_DEVICE_MAPPER) += device-mapper

#
# Paths and names
#
DEVICE_MAPPER_VERSION	:= 1.02.22
DEVICE_MAPPER		:= device-mapper.$(DEVICE_MAPPER_VERSION)
DEVICE_MAPPER_SUFFIX		:= tgz
DEVICE_MAPPER_URL		:= ftp://sources.redhat.com/pub/dm/$(DEVICE_MAPPER).$(DEVICE_MAPPER_SUFFIX)
DEVICE_MAPPER_SOURCE		:= $(SRCDIR)/$(DEVICE_MAPPER).$(DEVICE_MAPPER_SUFFIX)
DEVICE_MAPPER_DIR		:= $(BUILDDIR)/$(DEVICE_MAPPER)

# ----------------------------------------------------------------------------
# Get
# ----------------------------------------------------------------------------

device-mapper_get: $(STATEDIR)/device-mapper.get

$(STATEDIR)/device-mapper.get: $(device-mapper_get_deps_default)
	@$(call targetinfo, $@)
	@$(call touch, $@)

$(DEVICE_MAPPER_SOURCE):
	@$(call targetinfo, $@)
	@$(call get, DEVICE_MAPPER)

# ----------------------------------------------------------------------------
# Extract
# ----------------------------------------------------------------------------

device-mapper_extract: $(STATEDIR)/device-mapper.extract

$(STATEDIR)/device-mapper.extract: $(device-mapper_extract_deps_default)
	@$(call targetinfo, $@)
	@$(call clean, $(DEVICE_MAPPER_DIR))
	@$(call extract, DEVICE_MAPPER)
	@$(call patchin, DEVICE_MAPPER)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Prepare
# ----------------------------------------------------------------------------

device-mapper_prepare: $(STATEDIR)/device-mapper.prepare

DEVICE_MAPPER_PATH	:= PATH=$(CROSS_PATH)
DEVICE_MAPPER_ENV 	:= $(CROSS_ENV)

#
# autoconf
#
DEVICE_MAPPER_AUTOCONF := $(CROSS_AUTOCONF_USR)

$(STATEDIR)/device-mapper.prepare: $(device-mapper_prepare_deps_default)
	@$(call targetinfo, $@)
	@$(call clean, $(DEVICE_MAPPER_DIR)/config.cache)
	cd $(DEVICE_MAPPER_DIR) && \
		$(DEVICE_MAPPER_PATH) $(DEVICE_MAPPER_ENV) \
		./configure $(DEVICE_MAPPER_AUTOCONF)
	/bin/sed -ie '/rpl_malloc/d' $(DEVICE_MAPPER_DIR)/include/configure.h
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Compile
# ----------------------------------------------------------------------------

device-mapper_compile: $(STATEDIR)/device-mapper.compile

$(STATEDIR)/device-mapper.compile: $(device-mapper_compile_deps_default)
	@$(call targetinfo, $@)
	cd $(DEVICE_MAPPER_DIR) && $(DEVICE_MAPPER_PATH) $(MAKE) $(PARALLELMFLAGS)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Install
# ----------------------------------------------------------------------------

device-mapper_install: $(STATEDIR)/device-mapper.install

$(STATEDIR)/device-mapper.install: $(device-mapper_install_deps_default)
	@$(call targetinfo, $@)
	install -d $(SYSROOT)/usr/lib
	install $(DEVICE_MAPPER_DIR)/lib/ioctl/libdevmapper.a $(SYSROOT)/usr/lib
	install -d $(SYSROOT)/usr/include
	install -m 0644 $(DEVICE_MAPPER_DIR)/lib/libdevmapper.h $(SYSROOT)/usr/include
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Target-Install
# ----------------------------------------------------------------------------

device-mapper_targetinstall: $(STATEDIR)/device-mapper.targetinstall

$(STATEDIR)/device-mapper.targetinstall: $(device-mapper_targetinstall_deps_default)
	@$(call targetinfo, $@)

	@$(call install_init, device-mapper)
	@$(call install_fixup, device-mapper,PACKAGE,device-mapper)
	@$(call install_fixup, device-mapper,PRIORITY,optional)
	@$(call install_fixup, device-mapper,VERSION,$(DEVICE_MAPPER_VERSION))
	@$(call install_fixup, device-mapper,SECTION,base)
	@$(call install_fixup, device-mapper,AUTHOR,"Chuan-kai Lin <cklin\@google.com>")
	@$(call install_fixup, device-mapper,DEPENDS,)
	@$(call install_fixup, device-mapper,DESCRIPTION,missing)

	@$(call install_copy, device-mapper, 0, 0, 0644, $(DEVICE_MAPPER_DIR)/lib/ioctl/libdevmapper.so, /lib/libdevmapper.so.1.02)
	@$(call install_copy, device-mapper, 0, 0, 0755, $(DEVICE_MAPPER_DIR)/dmsetup/dmsetup, /sbin/dmsetup)

	@$(call install_finish, device-mapper)

	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Clean
# ----------------------------------------------------------------------------

device-mapper_clean:
	rm -rf $(STATEDIR)/device-mapper.*
	rm -rf $(IMAGEDIR)/device-mapper_*
	rm -rf $(DEVICE_MAPPER_DIR)

# vim: syntax=make
