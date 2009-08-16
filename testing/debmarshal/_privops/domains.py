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


import os

import libvirt

from debmarshal import errors
from debmarshal import hypervisors
from debmarshal._privops import networks
from debmarshal._privops import utils


def _validateNetwork(net, virt_con=None):
  """Validate a debmarshal network.

  This function checks that the network name passed in is a network
  known to (i.e. created by) debmarshal. It also verifies that the
  network was created by the user calling the function.

  Args:
    net: The name of the debmarshal network.
    virt_con: A read-only libvirt.virConnect instance. We'll open one
      of our own if one isn't passed in. Since libvirt network
      information is shared across all hypervisors, virt_con can be a
      connection to any libvirt driver.

  Raises:
    debmarshal.errors.NetworkNotFound if the named network doesn't
      exist.
    debmarshal.errors.AccessDenied if the network isn't owned by the
      caller.
  """
  if not virt_con:
    virt_con = libvirt.open('qemu:///system')

  nets = networks.loadNetworkState(virt_con)

  if net not in nets:
    raise errors.NetworkNotFound("Network %s does not exist." % net)

  if nets[net] != utils.getCaller():
    raise errors.AccessDenied("Network %s is not owned by UID %s." %
      (net, utils.getCaller()))


def _validatePath(path, perms):
  """Validate a disk image or other ifle.

  _validatePath makes sure that the user requesting a privileged
  operation would have permission to interact with the file in
  question.

  Args:
    disk: A path to a disk image
    perms: A bitmask composed of os.R_OK, os.W_OK, and/or os.X_OK

  Raises:
    debmarshal.errors.AccessDenied if the unprivileged user doesn't
      have permission to interact with the path using perms.
  """
  # Start by setting the process uid to getCaller(). This is primarily
  # done to make sure we're respecting the abstraction introduced by
  # getCaller().
  #
  # This won't guarantee that we have the necessary bits for, e.g.,
  # AFS, where you need a separate token to prove your identity, but
  # it would work for most other cases.
  old_uid = os.getuid()
  os.setreuid(utils.getCaller(), 0)

  try:
    if not os.access(path, perms):
      raise errors.AccessDenied('UID %s does not have access to %s.' %
                                (utils.getCaller(), path))
  finally:
    # Reset the process uid that we changed earlier.
    os.setuid(old_uid)


@utils.withoutLibvirtError
def _findUnusedName(virt_con):
  """Find a name for a new debmarshal domain.

  This picks a name for a new debmarshal domain by simply incrementing
  the name until a name is found that is not currently being used.

  In order to prevent races, this function should be called by a
  function that has taken the debmarshal-domlist lock exclusively.

  Args:
    virt_con: A read-only (or read-write) libvirt.virConnect instance
      connceted to the driver for which we want to find a name.

  Returns:
    An unused name to use for creating a new domain.
  """
  n = 0
  while True:
    name = 'debmarshal-%s' % n

    try:
      virt_con.lookupByName(name)
    except libvirt.libvirtError:
      return name

    n += 1


@utils.withoutLibvirtError
def loadDomainState():
  """Load stored state for domains previously created by debmarshal.

  State is stored in /var/run/debmarshal-domains. State is generally
  lost after reboots - which is good, since running domains tend to go
  away after reboots as well.

  Because not all distributions do this, and because domains can stop
  independent of debmarshal, we loop over the domains and erase our
  record of any domains that don't still exist.

  Each hypervisor has its own domain namespace. We'll need to open
  connections to multiple hypervisors, so there's no point passing a
  libvirt connection object in.

  Returns:
    A list of domains. Each domain is a tuple of (domain_name, owner
      hypervisor)
  """
  connections = {}

  domains = utils.loadState('debmarshal-domains')
  if not domains:
    return {}

  for dom, hypervisor in domains.keys():
    if hypervisor not in connections:
      hyper_class = hypervisors.base.hypervisors[hypervisor]
      connections[hypervisor] = hyper_class.open()

    try:
      connections[hypervisor].lookupByName(dom)
    except libvirt.libvirtError:
      del domains[(dom, hypervisor)]

  return domains
