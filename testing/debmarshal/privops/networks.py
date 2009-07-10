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

import libvirt
from lxml import etree
import virtinst

from debmarshal import errors
from debmarshal import ip
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


@utils.withoutLibvirtError
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

  for n in networks[:]:
    try:
      virt_con.networkLookupByName(n[0])
    except libvirt.libvirtError:
      networks.remove(n)

  return networks


def _networkBounds(gateway, netmask):
  """Find the start and end of available IP addresses in a network.

  Args:
    gateway: The gateway addresses of the network
    netmask: The netmask of the network

  Returns:
    Tuple of the form (low_ip, high_ip)
  """
  net = ip.IP('%s/%s' % (gateway, netmask))
  low = ip.IP(ip.IP(gateway).ip + 1)
  high = ip.IP(net.broadcast - 1)
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


@utils.withoutLibvirtError
def _findUnusedName(virt_con):
  """Find a name for a new debmarshal network.

  This picks a name for a new debmarshal network by simply
  incrementing the name until a name is found that is not currently
  being used.

  To prevent races, this function should be called by a function that
  has taken out the debmarshal-netlist lock exclusively.

  Args:
    virt_con: A read-only (or read-write) libvirt.virConnect instance
      connected to any driver.

  Returns:
    An unused name to use for creating a new network.
  """
  n = 0
  while True:
    name = 'debmarshal-%s' % n

    try:
      virt_con.networkLookupByName(name)
    except libvirt.libvirtError:
      return name

    n += 1


@utils.withoutLibvirtError
def _findUnusedNetwork(virt_con, host_count):
  """Find an IP address network for a new debmarshal network.

  This picks a gateway IP address by simply incrementing the subnet
  until one is found that is not currently being used.

  To prevent races, this function should be called by a function that
  has taken out the debmarshal-netlist lock exclusively.

  Currently IP addresses are allocated in /24 blocks from
  10.100.0.0/16. 100 was chosen both because it is the ASCII code for
  "d" and to try and avoid people using the lower subnets in 10/8.

  This does mean that debmarshal currently has an effective limit of
  256 test suites running simultaneously. But that also means that
  you'd be running at least 256 VMs simultaneously, which would
  require some pretty impressive hardware.

  Args:
    virt_con: A read-only (or read-write) libvirt.virConnect instance
      connected to any driver.
    host_count: How many hosts will be attached to this network.

  Returns:
    A network to use of the form (gateway, netmask)
  """
  # TODO(ebroder): Include the netmask of the libvirt networks when
  #   calculating available IP address space
  net_gateways = set()
  for net in virt_con.listNetworks() + virt_con.listDefinedNetworks():
    net_xml = etree.fromstring(virt_con.networkLookupByName(net).XMLDesc(0))
    net_gateways.add(net_xml.xpath('string(/network/ip/@address)'))

  for i in xrange(256):
    net = '10.100.%d.1' % i
    if net not in net_gateways:
      # TODO(ebroder): Adjust the size of the network based on the
      #   number of hosts that need to fit in it
      return (net, '255.255.255.0')

  raise errors.NoAvailableIPs('No unused subnet could be found.')


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
    _validateHostname(h)

  # We don't really care which particular libvirt driver we connect
  # to, because they all share the same networking
  # config. libvirt.open() is supposed to take None to indicate a
  # default, but it doesn't seem to work, so we pass in what's
  # supposed to be the default for root.
  virt_con = libvirt.open('qemu:///system')

  net_name = _findUnusedName(virt_con)
  net_gateway, net_mask = _findUnusedNetwork(virt_con, len(hosts))

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

  xml = _genNetworkXML(net_name, net_gateway, net_mask, net_hosts, dhcp)
  virt_net = virt_con.networkDefineXML(xml)
  virt_net.create()

  try:
    networks = loadNetworkState(virt_con)
    networks.append((net_name, utils.getCaller()))
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
