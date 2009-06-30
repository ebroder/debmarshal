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
"""debmarshal privileged virtual domain operations.

This module handles operations involving virtual machine domains, such
as booting or shutting down VMs.

This module does not deal with preparation of domains, such as
installing OS images.
"""


__authors__ = [
  'Evan Broder <ebroder@google.com>',
]


from debmarshal import errors
from debmarshal.privops import utils


@utils.runWithPrivilege('create-domain')
def createDomain(memory, disks, network, mac, hypervisor="qemu"):
  """Create a virtual machine domain.

  createDomain creates a domain for a virtual machine used as part of
  a debmarshal test and boots it up.

  We do no validation or accounting of memory allocations from the
  privileged side. Since debmarshal is intended to be run on
  single-user machines, the worst case scenario is a DoS of yourself.

  Args:
    memory: str containing the amount of memory to be allocated to the
      new domain. This should include a suffix such as 'G' or 'M' to
      indicate the units of the amount.
    disks: list of strs of paths to disk images, in the order that
      they should be attached to the guest. All disk images must be
      owned by the user calling createDomain.
    network: The name of the network to attach this VM to. The netwok
      must have been created using
      debmarshal.privops.networks.createNetwork by the user calling
      createDomain.
    mac: The MAC address of the new VM.
    hypervisor: What hypervisor to use to start this VM. While it's
      possible to mix hypervisors amongst the domains for a single
      test suite, it is the caller's responsibility to keep track of
      that when destroyDomain is called later. Currently only qemu is
      supported.
  """
  pass
