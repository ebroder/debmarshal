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


import fcntl
import os

import libvirt

from debmarshal import errors
from debmarshal import hypervisors
from debmarshal import vm
from debmarshal.privops import networks
from debmarshal.privops import utils


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

  for n in nets:
    if n[0] == net:
      break
  else:
    raise errors.NetworkNotFound("Network %s does not exist." % net)

  if n[1] != utils.getCaller():
    raise errors.AccessDenied("Network %s is not owned by UID %s." %
      (net, utils.getCaller()))


def _validateDisk(disk):
  """Validate a disk image.

  _validateDisk makes sure that the user requesting a privileged
  operation would have permission to read the disk.

  Args:
    disk: A path to a disk image

  Raises:
    debmarshal.errors.AccessDenied if the unprivileged user doesn't
      have permission to read from and write to the disk image.
  """
  # Start by setting the process uid to getCaller(). This is primarily
  # done to make sure we're respecting the abstraction introduced by
  # getCaller().
  #
  # This won't guarantee that we have the necessary bits for, e.g.,
  # AFS, where you need a separate token to prove your identity, but
  # it would work for most other cases.
  old_uid = os.getuid()
  os.setuid(utils.getCaller())

  try:
    if not os.access(disk, os.R_OK | os.W_OK):
      raise errors.AccessDenied('UID %s does not have access to %s.' %
                                (utils.getCaller(), disk))
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


_SUFFIXES = ['k', 'm', 'g', 't', 'p', 'e']


def _parseKBytes(amt):
  """Parse a human-readable byte measurement, such as '2G', into an
  int in kilobytes.

  _parseKBytes assumes that all suffixes are in binary units
  (multiples of 1024), as opposed to decimal units (multiples of
  1000).

  It recognizes single-letter suffixes ('G'), full-unit suffixes
  ('GB'), and explicitly binary SI suffixes ('GiB').

  Args:
    amt: str containing a human-readable byte measurement.

  Returns:
    An int with the same value is amt but measured in kilobytes.
  """
  amt = amt.lower()

  # We know that everything is in bytes; we don't need to hold onto
  # the B
  if amt.endswith('b'):
    amt = amt[:-1]

  # And all of the weird binary SI suffixes just stick a lowercase "i"
  # after the SI multiplier
  if amt.endswith('i'):
    amt = amt[:-1]

  # Now we have something we can work with
  suffix = amt[-1]
  significand = int(amt[:-1])

  # This is going to be off by one (i.e. kilobytes => 0 instead of 1),
  # but that's ok because we're returning a value in kilobytes anyway
  exp = _SUFFIXES.index(suffix)

  return significand * (1024 ** exp)


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
    return []

  for dom, uid, hypervisor in domains[:]:
    if hypervisor not in connections:
      hyper_class = hypervisors.base.hypervisors[hypervisor]
      connections[hypervisor] = hyper_class.open()

    try:
      connections[hypervisor].lookupByName(dom)
    except libvirt.libvirtError:
      domains.remove((dom, uid, hypervisor))

  return domains


def _createDomainXML(virt_con, xml):
  """Actually create a domain in libvirt in a version-independent way.

  At some point between libvirt 0.4 and the current version,
  libvirt.virConnect.createXML was given an extra argument. Since no
  version number information is exposed in the libvirt module, we have
  to guess how many arguments that method expects to take.

  Args:
    virt_con: Read-write connection to the libvirt driver with which
      the new domain should be created.
    xml: The XML specification for the domain to be created.
  """
  try:
    virt_con.createXML(xml, 0)
  except TypeError:
    virt_con.createXML(xml)


@utils.runWithPrivilege('create-domain')
@utils.withLockfile('debmarshal-domlist', fcntl.LOCK_EX)
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

  Returns:
    The name of the new domain.
  """
  hyper_class = hypervisors.base.hypervisors[hypervisor]
  virt_con = hyper_class.open()

  _validateNetwork(network, virt_con)
  for d in disks:
    _validateDisk(d)

  name = _findUnusedName(virt_con)
  memory = _parseKBytes(memory)

  vm_params = vm.VM(name=name,
                    memory=memory,
                    disks=disks,
                    network=network,
                    mac=mac)

  dom_xml = hyper_class.domainXMLString(vm_params)

  # The new domain is intentionally recorded to the statefile before
  # starting the VM, because it's much worse to have a running VM we
  # don't know about than to have state on a VM that doesn't actually
  # exist (loadDomainState already handles the latter case).
  doms = loadDomainState()
  doms.append((name, utils.getCaller(), hypervisor))
  utils.storeState(doms, 'debmarshal-domains')

  _createDomainXML(virt_con, dom_xml)

  return name

@utils.runWithPrivilege('destroy-domain')
@utils.withLockfile('debmarshal-domlist', fcntl.LOCK_EX)
def destroyDomain(name, hypervisor="qemu"):
  """Destroy a debmarshal domain.

  destroyDomain uses the state recorded by createDomain to verify
  ownership of the domain.

  Domains can be destroyed by the user that created them, or by root.

  Args:
    name: The name of the domain to destroy.
    hypervisor: The hypervisor for this domain.
  """
  hyper_class = hypervisors.base.hypervisors[hypervisor]
  virt_con = hyper_class.open()

  domains = loadDomainState()
  for dom in domains:
    if dom[0] == name and dom[2] == hypervisor:
      break
  else:
    raise errors.DomainNotFound("Domain %s does not exist." % name)

  if utils.getCaller() not in (0, dom[1]):
    raise errors.AccessDenied("Domain %s is not owned by UID %d." %
                              (name, utils.getCaller()))

  virt_dom = virt_con.lookupByName(name)
  virt_dom.destroy()

  domains.remove(dom)
  utils.storeState(domains, 'debmarshal-domains')
