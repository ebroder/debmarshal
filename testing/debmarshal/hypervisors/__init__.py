#!/usr/bin/python
# -*- python-indent: 2; py-indent-offset: 2 -*-
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
"""Hypervisor-specific configuration for debmarshal test domains.

The debmarshal.hypervisors package contains classes to help with any
specialized configuration required for the different virtualization
engines supported by debmarshal.

Note that because debmarshal.privops.domains uses
debmarshal.hypervisors to generate the libvirt XML for a domain,
debmarshal.hypervisors and all modules under it are trusted code.

In the root of the package, we load each submodule to make sure that
it's registered in debmarshal.hypervisors.base.hypervisors.
"""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


from debmarshal.hypervisors import base
from debmarshal.hypervisors import qemu
