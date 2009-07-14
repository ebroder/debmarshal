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

from dbus.mainloop import glib
import dbus.service
import decorator
import gobject
import libvirt
import virtinst

from debmarshal import errors
from debmarshal import hypervisors
from debmarshal import ip
from debmarshal import vm
from debmarshal._privops import domains
from debmarshal._privops import networks
from debmarshal._privops import utils


DBUS_INTERFACE='com.googlecode.debmarshal.Privops'


DBUS_BUS_NAME='com.googlecode.debmarshal'


DBUS_OBJECT_PATH='/com/googlecode/debmarshal/Privops'


_READY_TO_EXIT=False


@decorator.decorator
def _resetExitTimer(f, *args, **kwargs):
  """Decorator to reset the exit timer.

  This function resets _READY_TO_EXIT to False, indicating that a dbus
  message was received between the last and next calls to _maybeExit.
  """
  _READY_TO_EXIT=False
  return f(*args, **kwargs)


class Privops(dbus.service.Object):
  """Collection class for privileged dbus methods.

  All dbus methods should pass the sender_keyword option to the
  dbus.service.method decorator, and store that value to
  debmarshal.privops.utils.caller.

  It sucks that this has to be done by hand for each function, but
  it's not possible to use decorator-type metaprogramming with the
  dbus.service.method decorator because of the introspection it
  performs on method arguments.
  """
  Introspect = _resetExitTimer(dbus.service.Object.Introspect)

  @_resetExitTimer
  @dbus.service.method(DBUS_INTERFACE, sender_keyword='_debmarshal_sender',
                       in_signature='asb', out_signature='(sssa{s(ss)})')
  @utils.withLockfile('debmarshal-netlist', fcntl.LOCK_EX)
  def createNetwork(self, hosts, dhcp, _debmarshal_sender=None):
    """All of the networking config you need for a debmarshal test rig.

    createNetwork creates an isolated virtual network within
    libvirt. It picks an IP address space that is as-yet unused
    (within debmarshal), and assigns that to the network. It then
    allocates IP addresses and MAC addresses for each of the hostnames
    listed in hosts.

    createNetwork tracks which users created which networks, and
    debmarshal will only allow the user that created a network to
    attach VMs to it or destroy it.

    Args:
      hosts: A list of hostnames that will eventually be attached to
        this network
      dhcp: Whether to use DHCP or static IP addresses. If dhcp is
        True, createNetwork also configures dnsmasq listening on the
        new network to assign IP addresses

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
    utils.caller = _debmarshal_sender

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
      virt_con.networkLookupByName(net_name).destroy()
      virt_con.networkLookupByName(net_name).undefine()
      raise

    utils.caller = None

    return (net_name, net_gateway, net_mask, net_hosts)

  @_resetExitTimer
  @dbus.service.method(DBUS_INTERFACE, sender_keyword='_debmarshal_sender',
                       in_signature='s', out_signature='')
  @utils.withLockfile('debmarshal-netlist', fcntl.LOCK_EX)
  def destroyNetwork(self, name, _debmarshal_sender=None):
    """Destroy a debmarshal network.

    destroyNetwork uses the state recorded by createNetwork to verify
    that the user who created a network is the only one who can
    destroy it (except for root).

    Args:
      name: The name of the network returned from createNetwork

    Raises:
      debmarshal.errors.NetworkNotFound: The specified network name
        does not exist.
      debmarshal.errors.AccessDenied: The specified network is not
        owned by the user calling destroyNetwork.
    """
    utils.caller = _debmarshal_sender

    virt_con = libvirt.open('qemu:///system')

    nets = networks.loadNetworkState(virt_con)
    for net in nets:
      if net[0] == name:
        break
    else:
      raise errors.NetworkNotFound("Network %s does not exist." % name)

    if utils.getCaller() not in (0, net[1]):
      raise errors.AccessDenied("Network %s not owned by UID %d." % (name, utils.getCaller()))

    virt_con.networkLookupByName(name).destroy()
    virt_con.networkLookupByName(name).undefine()

    nets.remove(net)
    utils.storeState(nets, 'debmarshal-networks')

    utils.caller = None

  @_resetExitTimer
  @dbus.service.method(DBUS_INTERFACE, sender_keyword='_debmarshal_sender',
                       in_signature='sassss', out_signature='s')
  @utils.withLockfile('debmarshal-domlist', fcntl.LOCK_EX)
  def createDomain(self, memory, disks, network, mac, hypervisor,
                   _debmarshal_sender=None):
    """Create a virtual machine domain.

    createDomain creates a domain for a virtual machine used as part
    of a debmarshal test and boots it up.

    We do no validation or accounting of memory allocations from the
    privileged side. Since debmarshal is intended to be run on
    single-user machines, the worst case scenario is a DoS of
    yourself.

    Args:
      memory: str containing the amount of memory to be allocated to
        the new domain. This should include a suffix such as 'G' or
        'M' to indicate the units of the amount.
      disks: list of strs of paths to disk images, in the order that
        they should be attached to the guest. All disk images must be
        owned by the user calling createDomain.
      network: The name of the network to attach this VM to. The
        netwok must have been created using
        debmarshal.privops.createNetwork by the user calling
        createDomain.
      mac: The MAC address of the new VM.
      hypervisor: What hypervisor to use to start this VM. While it's
        possible to mix hypervisors amongst the domains for a single
        test suite, it is the caller's responsibility to keep track of
        that when destroyDomain is called later. Currently only qemu
        is supported.

    Returns:
      The name of the new domain.
    """
    utils.caller = _debmarshal_sender

    hyper_class = hypervisors.base.hypervisors[hypervisor]
    virt_con = hyper_class.open()

    domains._validateNetwork(network, virt_con)
    for d in disks:
      domains._validateDisk(d)

    name = domains._findUnusedName(virt_con)
    memory = domains._parseKBytes(memory)

    vm_params = vm.VM(name=name,
                      memory=memory,
                      disks=disks,
                      network=network,
                      mac=mac)

    dom_xml = hyper_class.domainXMLString(vm_params)

    # The new domain is intentionally recorded to the statefile before
    # starting the VM, because it's much worse to have a running VM we
    # don't know about than to have state on a VM that doesn't
    # actually exist (loadDomainState already handles the latter
    # case).
    doms = domains.loadDomainState()
    doms.append((name, utils.getCaller(), hypervisor))
    utils.storeState(doms, 'debmarshal-domains')

    domains._createDomainXML(virt_con, dom_xml)

    utils.caller = None

    return name

  @_resetExitTimer
  @dbus.service.method(DBUS_INTERFACE, sender_keyword='_debmarshal_sender',
                       in_signature='ss', out_signature='')
  @utils.withLockfile('debmarshal-domlist', fcntl.LOCK_EX)
  def destroyDomain(self, name, hypervisor, _debmarshal_sender=None):
    """Destroy a debmarshal domain.

    destroyDomain uses the state recorded by createDomain to verify
    ownership of the domain.

    Domains can be destroyed by the user that created them, or by
    root.

    Args:
      name: The name of the domain to destroy.
      hypervisor: The hypervisor for this domain.
    """
    utils.caller = _debmarshal_sender

    hyper_class = hypervisors.base.hypervisors[hypervisor]
    virt_con = hyper_class.open()

    doms = domains.loadDomainState()
    for dom in doms:
      if dom[0] == name and dom[2] == hypervisor:
        break
    else:
      raise errors.DomainNotFound("Domain %s does not exist." % name)

    if utils.getCaller() not in (0, dom[1]):
      raise errors.AccessDenied("Domain %s is not owned by UID %d." %
                                (name, utils.getCaller()))

    virt_dom = virt_con.lookupByName(name)
    virt_dom.destroy()

    doms.remove(dom)
    utils.storeState(doms, 'debmarshal-domains')

    utils.caller = None


def call(method, *args):
  """Call a privileged operation.

  This function handles calling privileged operations. Currently,
  these calls are simply dispatched over dbus.

  Args:
    method: The name of the method to call.
    *args: The arguments to pass to the method.
  """
  proxy = dbus.SystemBus().get_object(DBUS_BUS_NAME, DBUS_OBJECT_PATH)
  return proxy.get_dbus_method(method, dbus_interface=DBUS_INTERFACE)(*args)


def _maybeExit(loop):
  """Exit if there were no methods called in the last second.

  DBus proxy objects are associated with a connection to a specific
  non-well-known bus name. If the main loop was configured to exit as
  soon as there were no pending tasks, there would be a race
  condition. Calls from the Python bindings first make an Introspect
  call before calling the actual method, and the idle hook might
  trigger between those two calls.

  With _maybeExit, the main loop will only exit if there have been no
  dbus methods called in the last 10 seconds. There's still a
  potential race here. But if your bindings try to reuse a connection,
  but are so slow that they wait for a whole seconds between the
  Introspection and the actual method, it just sucks to be you.

  Args:
    loop: The gobject.MainLoop that we will quit if no dbus methods
      were called.
  """
  global _READY_TO_EXIT

  if _READY_TO_EXIT:
    loop.quit()
  else:
    _READY_TO_EXIT=True

  return True


def main():
  """Main loop for the dbus service.

  This creates an instance of the Privops object at the
  DBUS_OBJECT_PATH, connecting it to a service with DBUS_BUS_NAME on
  the system bus.
  """
  glib.DBusGMainLoop(set_as_default=True)
  name = dbus.service.BusName(DBUS_BUS_NAME, dbus.SystemBus())
  dbus_obj = Privops(name, DBUS_OBJECT_PATH)
  loop = gobject.MainLoop()
  gobject.timeout_add_seconds(1, _maybeExit, loop)
  loop.run()


if __name__ == '__main__':  # pragma: no cover
  main()
