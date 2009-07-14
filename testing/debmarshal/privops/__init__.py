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
"""debmarshal setuid support module.

This module provides the necessary input sanitation and command
wrappers to allow debmarshal test suites to be run by unprivileged
users.

The main privileged operations for VM-based test suites is the
networking configuration. Depending on the virtualization technology
being used, this may also include creating the guest domain, so we'll
cover that here as well.

Although debmarshal is currently using libvirt to reduce the amount of
code needed, we won't be accepting libvirt's XML config format for
these privileged operations. This both limits the range of inputs we
have to sanitize and makes it easier to switch away from libvirt in
the future.
"""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import fcntl

import libvirt
import virtinst

from debmarshal import errors
from debmarshal import ip
from debmarshal.privops import domains
from debmarshal.privops import networks
from debmarshal.privops import utils


@utils.runWithPrivilege('create-network')
@utils.withLockfile('debmarshal-netlist', fcntl.LOCK_EX)
def createNetwork(hosts, dhcp=True):
  """All of the networking config you need for a debmarshal test rig.

  createNetwork creates an isolated virtual network within libvirt. It
  picks an IP address space that is as-yet unused (within debmarshal),
  and assigns that to the network. It then allocates IP addresses and
  MAC addresses for each of the hostnames listed in hosts.

  createNetwork tracks which users created which networks, and
  debmarshal will only allow the user that created a network to attach
  VMs to it or destroy it.

  Args:
    hosts: A list of hostnames that will eventually be attached to
      this network
    dhcp: Whether to use DHCP or static IP addresses. If dhcp is True
      (the default), createNetwork also configures dnsmasq listening
      on the new network to assign IP addresses

  Returns:
    A 4-tuple containing:
      Network name: This is used to reference the newly created
        network in the future. It is unique across the local
        workstation
      Gateway: The network address. Also the DNS server, if that
        information isn't being grabbed over DHCP
      Netmask: The netmask for the network
      VMs: A dict mapping hostnames in hosts to (IP address, MAC
        address), as assigned by createNetwork
  """
  # First, input validation. Everything in hosts should be a valid
  # hostname
  for h in hosts:
    networks._validateHostname(h)

  # We don't really care which particular libvirt driver we connect
  # to, because they all share the same networking
  # config. libvirt.open() is supposed to take None to indicate a
  # default, but it doesn't seem to work, so we pass in what's
  # supposed to be the default for root.
  virt_con = libvirt.open('qemu:///system')

  net_name = networks._findUnusedName(virt_con)
  net_gateway, net_mask = networks._findUnusedNetwork(virt_con, len(hosts))

  net_hosts = {}
  host_addr = ip.IP(net_gateway) + 1
  for host in hosts:
    # Use the virtinst package's MAC address generator because it's
    # easier than writing another one for ourselves.
    #
    # This does mean that the MAC addresses are allocated from
    # Xensource's OUI, but whatever
    mac = virtinst.util.randomMAC()
    net_hosts[host] = (host_addr.ip_ext, mac)
    host_addr += 1

  xml = networks._genNetworkXML(net_name, net_gateway, net_mask, net_hosts, dhcp)
  virt_net = virt_con.networkDefineXML(xml)
  virt_net.create()

  try:
    nets = networks.loadNetworkState(virt_con)
    nets.append((net_name, utils.getCaller()))
    utils.storeState(nets, 'debmarshal-networks')
  except:
    virt_net.destroy()
    virt_net.undefine()
    raise

  return (net_name, net_gateway, net_mask, net_hosts)


@utils.runWithPrivilege('destroy-network')
@utils.withLockfile('debmarshal-netlist', fcntl.LOCK_EX)
def destroyNetwork(name):
  """Destroy a debmarshal network.

  destroyNetwork uses the state recorded by createNetwork to verify
  that the user who created a network is the only one who can destroy
  it (except for root).

  Args:
    name: The name of the network returned from createNetwork

  Raises:
    debmarshal.errors.NetworkNotFound: The specified network name does
      not exist.
    debmarshal.errors.AccessDenied: The specified network is not owned
      by the user calling destroyNetwork.
  """
  virt_con = libvirt.open('qemu:///system')

  nets = networks.loadNetworkState(virt_con)
  for net in nets:
    if net[0] == name:
      break
  else:
    raise errors.NetworkNotFound("Network %s does not exist." % name)

  if utils.getCaller() not in (0, net[1]):
    raise errors.AccessDenied("Network %s not owned by UID %d." % (name, utils.getCaller()))

  virt_net = virt_con.networkLookupByName(name)
  virt_net.destroy()
  virt_net.undefine()

  nets.remove(net)
  utils.storeState(nets, 'debmarshal-networks')


if __name__ == '__main__':  # pragma: no cover
  sys.exit(utils.main(sys.argv[1:]))
