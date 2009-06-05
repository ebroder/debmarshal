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
PACKAGES-$(PTXCONF_LVM2) += lvm2

#
# Paths and names
#
LVM2_VERSION	:= 2.02.27
LVM2		:= LVM2.$(LVM2_VERSION)
LVM2_SUFFIX		:= tgz
LVM2_URL		:= ftp://sources.redhat.com/pub/lvm2/$(LVM2).$(LVM2_SUFFIX)
LVM2_SOURCE		:= $(SRCDIR)/$(LVM2).$(LVM2_SUFFIX)
LVM2_DIR		:= $(BUILDDIR)/$(LVM2)

# ----------------------------------------------------------------------------
# Get
# ----------------------------------------------------------------------------

lvm2_get: $(STATEDIR)/lvm2.get

$(STATEDIR)/lvm2.get: $(lvm2_get_deps_default)
	@$(call targetinfo, $@)
	@$(call touch, $@)

$(LVM2_SOURCE):
	@$(call targetinfo, $@)
	@$(call get, LVM2)

# ----------------------------------------------------------------------------
# Extract
# ----------------------------------------------------------------------------

lvm2_extract: $(STATEDIR)/lvm2.extract

$(STATEDIR)/lvm2.extract: $(lvm2_extract_deps_default)
	@$(call targetinfo, $@)
	@$(call clean, $(LVM2_DIR))
	@$(call extract, LVM2)
	@$(call patchin, LVM2)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Prepare
# ----------------------------------------------------------------------------

lvm2_prepare: $(STATEDIR)/lvm2.prepare

LVM2_PATH	:= PATH=$(CROSS_PATH)
LVM2_ENV 	:= $(CROSS_ENV)

#
# autoconf
#
LVM2_AUTOCONF := $(CROSS_AUTOCONF_USR)

$(STATEDIR)/lvm2.prepare: $(lvm2_prepare_deps_default)
	@$(call targetinfo, $@)
	@$(call clean, $(LVM2_DIR)/config.cache)
	cd $(LVM2_DIR) && \
		$(LVM2_PATH) $(LVM2_ENV) \
		./configure $(LVM2_AUTOCONF)
	/bin/sed -ie '/rpl_malloc/d' $(LVM2_DIR)/lib/misc/configure.h
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Compile
# ----------------------------------------------------------------------------

lvm2_compile: $(STATEDIR)/lvm2.compile

$(STATEDIR)/lvm2.compile: $(lvm2_compile_deps_default)
	@$(call targetinfo, $@)
	cd $(LVM2_DIR) && $(LVM2_PATH) $(LVM2_ENV) $(MAKE) $(PARALLELMFLAGS)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Install
# ----------------------------------------------------------------------------

lvm2_install: $(STATEDIR)/lvm2.install

$(STATEDIR)/lvm2.install: $(lvm2_install_deps_default)
	@$(call targetinfo, $@)
	@$(call install, LVM2)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Target-Install
# ----------------------------------------------------------------------------

lvm2_targetinstall: $(STATEDIR)/lvm2.targetinstall

$(STATEDIR)/lvm2.targetinstall: $(lvm2_targetinstall_deps_default)
	@$(call targetinfo, $@)

	@$(call install_init, lvm2)
	@$(call install_fixup, lvm2,PACKAGE,lvm2)
	@$(call install_fixup, lvm2,PRIORITY,optional)
	@$(call install_fixup, lvm2,VERSION,$(LVM2_VERSION))
	@$(call install_fixup, lvm2,SECTION,base)
	@$(call install_fixup, lvm2,AUTHOR,"Chuan-kai Lin <cklin\@google.com>")
	@$(call install_fixup, lvm2,DEPENDS,)
	@$(call install_fixup, lvm2,DESCRIPTION,missing)

	@$(call install_copy, lvm2, 0, 0, 0755, $(LVM2_DIR)/tools/lvm, /sbin/lvm)
	@$(call install_link, lvm2, lvm, /sbin/lvchange)
	@$(call install_link, lvm2, lvm, /sbin/lvconvert)
	@$(call install_link, lvm2, lvm, /sbin/lvcreate)
	@$(call install_link, lvm2, lvm, /sbin/lvdisplay)
	@$(call install_link, lvm2, lvm, /sbin/lvextend)
	@$(call install_link, lvm2, lvm, /sbin/lvmchange)
	@$(call install_link, lvm2, lvm, /sbin/lvmdiskscan)
	@$(call install_link, lvm2, lvm, /sbin/lvmsadc)
	@$(call install_link, lvm2, lvm, /sbin/lvmsar)
	@$(call install_link, lvm2, lvm, /sbin/lvreduce)
	@$(call install_link, lvm2, lvm, /sbin/lvremove)
	@$(call install_link, lvm2, lvm, /sbin/lvrename)
	@$(call install_link, lvm2, lvm, /sbin/lvresize)
	@$(call install_link, lvm2, lvm, /sbin/lvs)
	@$(call install_link, lvm2, lvm, /sbin/lvscan)
	@$(call install_link, lvm2, lvm, /sbin/pvchange)
	@$(call install_link, lvm2, lvm, /sbin/pvcreate)
	@$(call install_link, lvm2, lvm, /sbin/pvdisplay)
	@$(call install_link, lvm2, lvm, /sbin/pvmove)
	@$(call install_link, lvm2, lvm, /sbin/pvremove)
	@$(call install_link, lvm2, lvm, /sbin/pvresize)
	@$(call install_link, lvm2, lvm, /sbin/pvs)
	@$(call install_link, lvm2, lvm, /sbin/pvscan)
	@$(call install_link, lvm2, lvm, /sbin/vgcfgbackup)
	@$(call install_link, lvm2, lvm, /sbin/vgcfgrestore)
	@$(call install_link, lvm2, lvm, /sbin/vgchange)
	@$(call install_link, lvm2, lvm, /sbin/vgck)
	@$(call install_link, lvm2, lvm, /sbin/vgconvert)
	@$(call install_link, lvm2, lvm, /sbin/vgcreate)
	@$(call install_link, lvm2, lvm, /sbin/vgdisplay)
	@$(call install_link, lvm2, lvm, /sbin/vgexport)
	@$(call install_link, lvm2, lvm, /sbin/vgextend)
	@$(call install_link, lvm2, lvm, /sbin/vgimport)
	@$(call install_link, lvm2, lvm, /sbin/vgmerge)
	@$(call install_link, lvm2, lvm, /sbin/vgmknodes)
	@$(call install_link, lvm2, lvm, /sbin/vgreduce)
	@$(call install_link, lvm2, lvm, /sbin/vgremove)
	@$(call install_link, lvm2, lvm, /sbin/vgrename)
	@$(call install_link, lvm2, lvm, /sbin/vgs)
	@$(call install_link, lvm2, lvm, /sbin/vgscan)
	@$(call install_link, lvm2, lvm, /sbin/vgsplit)

	@$(call install_finish, lvm2)

	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Clean
# ----------------------------------------------------------------------------

lvm2_clean:
	rm -rf $(STATEDIR)/lvm2.*
	rm -rf $(IMAGEDIR)/lvm2_*
	rm -rf $(LVM2_DIR)

# vim: syntax=make
