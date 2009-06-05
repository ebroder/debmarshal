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
PACKAGES-$(PTXCONF_TREE) += tree

#
# Paths and names
#
TREE_VERSION	:= 1.5.1.1
TREE		:= tree-$(TREE_VERSION)
TREE_SUFFIX		:= tgz
TREE_URL		:= http://mama.indstate.edu/users/ice/tree/$(TREE).$(TREE_SUFFIX)
TREE_SOURCE		:= $(SRCDIR)/$(TREE).$(TREE_SUFFIX)
TREE_DIR		:= $(BUILDDIR)/$(TREE)

# ----------------------------------------------------------------------------
# Get
# ----------------------------------------------------------------------------

tree_get: $(STATEDIR)/tree.get

$(STATEDIR)/tree.get: $(tree_get_deps_default)
	@$(call targetinfo, $@)
	@$(call touch, $@)

$(TREE_SOURCE):
	@$(call targetinfo, $@)
	@$(call get, TREE)

# ----------------------------------------------------------------------------
# Extract
# ----------------------------------------------------------------------------

tree_extract: $(STATEDIR)/tree.extract

$(STATEDIR)/tree.extract: $(tree_extract_deps_default)
	@$(call targetinfo, $@)
	@$(call clean, $(TREE_DIR))
	@$(call extract, TREE)
	@$(call patchin, TREE)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Prepare
# ----------------------------------------------------------------------------

tree_prepare: $(STATEDIR)/tree.prepare

TREE_PATH	:= PATH=$(CROSS_PATH)
TREE_ENV 	:= $(CROSS_ENV)

#
# autoconf
#
TREE_AUTOCONF := $(CROSS_AUTOCONF_USR)

$(STATEDIR)/tree.prepare: $(tree_prepare_deps_default)
	@$(call targetinfo, $@)
	@$(call clean, $(TREE_DIR)/config.cache)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Compile
# ----------------------------------------------------------------------------

tree_compile: $(STATEDIR)/tree.compile

$(STATEDIR)/tree.compile: $(tree_compile_deps_default)
	@$(call targetinfo, $@)
	cd $(TREE_DIR) && $(TREE_PATH) $(MAKE) $(PARALLELMFLAGS)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Install
# ----------------------------------------------------------------------------

tree_install: $(STATEDIR)/tree.install

$(STATEDIR)/tree.install: $(tree_install_deps_default)
	@$(call targetinfo, $@)
	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Target-Install
# ----------------------------------------------------------------------------

tree_targetinstall: $(STATEDIR)/tree.targetinstall

$(STATEDIR)/tree.targetinstall: $(tree_targetinstall_deps_default)
	@$(call targetinfo, $@)

	@$(call install_init, tree)
	@$(call install_fixup, tree,PACKAGE,tree)
	@$(call install_fixup, tree,PRIORITY,optional)
	@$(call install_fixup, tree,VERSION,$(TREE_VERSION))
	@$(call install_fixup, tree,SECTION,base)
	@$(call install_fixup, tree,AUTHOR,"Chuan-kai Lin <cklin\@google.com>")
	@$(call install_fixup, tree,DEPENDS,)
	@$(call install_fixup, tree,DESCRIPTION,missing)

	@$(call install_copy, tree, 0, 0, 0755, $(TREE_DIR)/tree, /usr/bin/tree)

	@$(call install_finish, tree)

	@$(call touch, $@)

# ----------------------------------------------------------------------------
# Clean
# ----------------------------------------------------------------------------

tree_clean:
	rm -rf $(STATEDIR)/tree.*
	rm -rf $(IMAGEDIR)/tree_*
	rm -rf $(TREE_DIR)

# vim: syntax=make
