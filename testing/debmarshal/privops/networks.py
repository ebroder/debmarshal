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
"""debmarshal privileged networking operations

This module handles creating and destroying virtual networks that are
used for debmarshal test suites.
"""

__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import fcntl
import itertools
try:
  import cPickle as pickle
except ImportError:  # pragma: no cover
  import pickle
import re

import ipaddr
import libvirt
from lxml import etree
import virtinst

from debmarshal import errors
from debmarshal.privops import utils


_hostname_re = re.compile(r"([a-z0-9][a-z0-9-]{0,62}\.)+([a-z]{2,4})$", re.I)
def _validateHostname(name):
  """Check that the input is a valid, fully-qualified domain name

  Args:
    name: The hostname to validate

  Returns:
    None

  Raises:
    debmarshal.errors.InvalidInput if the hostname is not valid
  """
  if not _hostname_re.match(name):
    raise errors.InvalidInput('Invalid hostname: %s' % name)


def loadNetworkState(virt_con=None):
  """Load state for any networks previously created by debmarshal.

  State is written to /var/run/debmarshal-networks as a pickle. Ubuntu
  makes /var/run a tmpfs, so state vanishes after reboots - which is
  good, because the networks debmarshal has created do as well.

  Not all distributions do this, though, so we loop over the networks
  in the pickle and see which ones still exist. If a network no longer
  exists, we assume that it was deleted outside of debmarshal, and we
  erase our record of it.

  Args:
    virt_con: A non-read-only libvirt.virConnect instance. If one
      isn't passed in, we'll open one of our own. It doesn't really
      matter which libvirt driver you connect to, because all of them
      share virtual networks.

  Returns:
    A list of networks. Each network is a tuple of (network_name,
      owner_uid, gateway_ip_address)
  """
  networks = utils.loadState('debmarshal-networks')
  if not networks:
    networks = []

  if not virt_con:
    virt_con = libvirt.open('qemu:///system')

  # The default handler for any libvirt error prints to stderr. In
  # this case, we're trying to trigger an error, so we don't want
  # the printout. This suppresses the printout temporarily
  libvirt.registerErrorHandler((lambda ctx, err: 1), None)

  for n in networks[:]:
    try:
      virt_con.networkLookupByName(n[0])
    except libvirt.libvirtError:
      networks.remove(n)

  # Reset the error handler to its default
  libvirt.registerErrorHandler(None, None)

  return networks


def _networkBounds(gateway, netmask):
  """Find the start and end of available IP addresses in a network.

  Args:
    gateway: The gateway addresses of the network
    netmask: The netmask of the network

  Returns:
    Tuple of the form (low_ip, high_ip)
  """
  net = ipaddr.IP('%s/%s' % (gateway, netmask))
  low = ipaddr.IP(ipaddr.IP(gateway).ip + 1)
  high = ipaddr.IP(net.broadcast - 1)
  return (low.ip_ext, high.ip_ext)


def _genNetworkXML(name, gateway, netmask, hosts, dhcp):
  """Given parameters for a debmarshal network, generate the libvirt
  XML specification.

  Args:
    name: Name of the network, usually debmarshal-##
    gateway: The "gateway" for the network. Although debmarshal
      networks are isolated, you still need a gateway for things like
      the DHCP server to live at
    netmask
    hosts: The hosts that will be attached to this network. It is a
      dict from hostnames to a 2-tuple of (IP address, MAC address),
      similar to the one that's returned from createNetwork
    dhcp: A bool indicating whether or not to run DHCP on the new
      network

  Returns:
    The string representation of the libvirt XML network matching the
      parameters passed in
  """
  xml = etree.Element('network')
  etree.SubElement(xml, 'name').text = name
  xml_ip = etree.SubElement(xml, 'ip',
                            address=gateway,
                            netmask=netmask)

  if dhcp:
    low, high = _networkBounds(gateway, netmask)

    xml_dhcp = etree.SubElement(xml_ip, 'dhcp')
    etree.SubElement(xml_dhcp, 'range',
                     start=low,
                     end=high)

    for hostname, hostinfo in hosts.iteritems():
      etree.SubElement(xml_dhcp, 'host',
                       name=hostname,
                       ip=hostinfo[0],
                       mac=hostinfo[1])

  return etree.tostring(xml)


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

  Currently IP addresses are allocated in /24 blocks from
  10.100.0.0/16. 100 was chosen both because it is the ASCII code for
  "d" and to try and avoid people using the lower subnets in 10/8.

  This does mean that debmarshal currently has an effective limit of
  256 test suites running simultaneously. But that also means that
  you'd be running at least 256 VMs simultaneously, which would
  require some pretty impressive hardware.

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
    _validateHostname(h)

  # We don't really care which particular libvirt driver we connect
  # to, because they all share the same networking
  # config. libvirt.open() is supposed to take None to indicate a
  # default, but it doesn't seem to work, so we pass in what's
  # supposed to be the default for root.
  virt_con = libvirt.open('qemu:///system')

  networks = loadNetworkState(virt_con)
  net_names = set(n[0] for n in networks)
  net_gateways = set(n[2] for n in networks)

  # Now we actually can allocate the new network.
  #
  # First, let's figure out what to call this network
  for i in itertools.count(0):
    net_name = 'debmarshal-%d' % i
    if net_name not in net_names:
      break

  # Then find a network to assign
  #
  # TODO(ebroder): Error out if we can't find an open address space to
  #   use. Right now this block will happily assign 10.100.256.1 to a
  #   new network.
  for net in itertools.count(0):
    net_gateway = '10.100.%d.1' % net
    if net_gateway not in net_gateways:
      break

  # Assign IP addresses and MAC addresses for every host that's
  # supposed to end up on this network
  net_hosts = {}
  i = 2
  for host in hosts:
    # Use the virtinst package's MAC address generator because it's
    # easier than writing another one for ourselves.
    #
    # This does mean that the MAC addresses are allocated from
    # Xensource's OUI, but whatever
    mac = virtinst.util.randomMAC()
    ip = '10.100.%d.%d' % (net, i)
    net_hosts[host] = (ip, mac)
    i += 1

  net_mask = '255.255.255.0'

  xml = _genNetworkXML(net_name, net_gateway, net_mask, net_hosts, dhcp)
  virt_net = virt_con.networkDefineXML(xml)
  virt_net.create()
  networks.append((net_name, utils.getCaller(), net_gateway))

  # Record the network information into our state file
  try:
    utils.storeState(networks, 'debmarshal-networks')
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
  """
  virt_con = libvirt.open('qemu:///system')

  networks = loadNetworkState(virt_con)
  for net in networks:
    if net[0] == name:
      break
  else:
    raise errors.NetworkNotFound("Network %s does not exist." % name)

  if utils.getCaller() not in (0, net[1]):
    raise errors.AccessDenied("Network %s not owned by UID %d." % (name, utils.getCaller()))

  virt_net = virt_con.networkLookupByName(name)
  virt_net.destroy()
  virt_net.undefine()

  networks.remove(net)
  utils.storeState(networks, 'debmarshal-networks')
