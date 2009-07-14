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
"""Tests for debmarshal.privops."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import fcntl
import os
import unittest

import dbus
import dbus.bus
import dbus.mainloop.glib
import dbus.service
import gobject
import libvirt
import mox
import virtinst

from debmarshal import errors
from debmarshal import hypervisors
from debmarshal import privops
from debmarshal.privops import domains
from debmarshal.privops import networks
from debmarshal.privops import utils


class TestCreateNetwork(mox.MoxTestBase):
  """Test debmarshal.privops.createNetwork."""
  def setUp(self):
    """The only two interesting conditions to test here are whether
    storeState raises an exception or not, so let's commonize
    everything else"""
    super(TestCreateNetwork, self).setUp()

    self.networks = [('debmarshal-0', 500),
                     ('debmarshal-3', 500),
                     ('debmarshal-4', 500),
                     ('debmarshal-4', 500)]
    self.name = 'debmarshal-1'
    self.gateway = '10.100.3.1'
    self.hosts = ['wiki.company.com', 'login.company.com']
    self.host_dict = {'wiki.company.com':
                      ('10.100.3.2', '00:00:00:00:00:00'),
                      'login.company.com':
                      ('10.100.3.3', '00:00:00:00:00:00')}

    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().AndReturn(1000)

    self.mox.StubOutWithMock(utils, '_acquireLock')
    utils._acquireLock('debmarshal-netlist', fcntl.LOCK_EX)

    self.mox.StubOutWithMock(networks, '_validateHostname')
    networks._validateHostname(mox.IgnoreArg()).MultipleTimes()

    self.mox.StubOutWithMock(libvirt, 'open')
    virt_con = self.mox.CreateMock(libvirt.virConnect)
    libvirt.open(mox.IgnoreArg()).AndReturn(virt_con)

    self.mox.StubOutWithMock(networks, '_findUnusedName')
    networks._findUnusedName(virt_con).AndReturn(self.name)

    self.mox.StubOutWithMock(networks, '_findUnusedNetwork')
    networks._findUnusedNetwork(virt_con, len(self.hosts)).\
        AndReturn((self.gateway, '255.255.255.0'))

    self.mox.StubOutWithMock(networks, 'loadNetworkState')
    networks.loadNetworkState(virt_con).AndReturn(self.networks)

    self.mox.StubOutWithMock(virtinst.util, 'randomMAC')
    virtinst.util.randomMAC().MultipleTimes().AndReturn('00:00:00:00:00:00')

    self.mox.StubOutWithMock(networks, '_genNetworkXML')
    networks._genNetworkXML(self.name, self.gateway, '255.255.255.0',
                           self.host_dict, False).AndReturn('<fake_xml />')

    self.virt_net = self.mox.CreateMock(libvirt.virNetwork)
    virt_con.networkDefineXML('<fake_xml />').AndReturn(self.virt_net)
    self.virt_net.create()

  def testStoreSuccess(self):
    """Test createNetwork when everything goes right"""
    self.mox.StubOutWithMock(utils, 'storeState')
    utils.storeState(self.networks +
                     [(self.name, 1000)],
                     'debmarshal-networks')

    self.mox.ReplayAll()

    self.assertEqual(privops.Privops().createNetwork(self.hosts, False),
                     (self.name, self.gateway, '255.255.255.0', self.host_dict))

  def testStoreFailure(self):
    """Test that the network is destroyed if state about it can't be
    stored"""
    self.mox.StubOutWithMock(utils, 'storeState')
    utils.storeState(self.networks +
                     [(self.name, 1000)],
                     'debmarshal-networks').\
                     AndRaise(Exception("Error!"))

    self.virt_net.destroy()
    self.virt_net.undefine()

    self.mox.ReplayAll()

    self.assertRaises(Exception, privops.Privops().createNetwork,
                      self.hosts, False)


class TestDestroyNetwork(mox.MoxTestBase):
  def setUp(self):
    """Setup some mocks common to all tests of destroyNetwork"""
    super(TestDestroyNetwork, self).setUp()

    self.mox.StubOutWithMock(utils, '_acquireLock')
    utils._acquireLock('debmarshal-netlist', fcntl.LOCK_EX)

    self.mox.StubOutWithMock(libvirt, 'open')
    self.virt_con = self.mox.CreateMock(libvirt.virConnect)
    libvirt.open(mox.IgnoreArg()).AndReturn(self.virt_con)

    self.networks = [('debmarshal-0', 501),
                     ('debmarshal-1', 500)]
    self.mox.StubOutWithMock(networks, 'loadNetworkState')
    networks.loadNetworkState(self.virt_con).AndReturn(self.networks)

  def testNoNetwork(self):
    """Test that destroyNetwork doesn't try to delete a network it
    doesn't know about"""
    self.mox.ReplayAll()

    self.assertRaises(errors.NetworkNotFound, privops.Privops().destroyNetwork,
                      'debmarshal-3')

  def testNoPermissions(self):
    """Test that destroyNetwork refuses to delete a network if you
    don't own it"""
    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().MultipleTimes().AndReturn(501)

    self.mox.ReplayAll()

    self.assertRaises(errors.AccessDenied, privops.Privops().destroyNetwork,
                      'debmarshal-1')

  def testSuccess(self):
    """Test that destroyNetwork will actually delete an existing
    network owned by the right user."""
    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().MultipleTimes().AndReturn(501)

    virt_net = self.mox.CreateMock(libvirt.virNetwork)
    self.virt_con.networkLookupByName('debmarshal-0').AndReturn(virt_net)
    virt_net.destroy()
    virt_net.undefine()

    self.mox.StubOutWithMock(utils, 'storeState')
    new_networks = self.networks[1:]
    utils.storeState(new_networks, 'debmarshal-networks')

    self.mox.ReplayAll()

    privops.Privops().destroyNetwork('debmarshal-0')


class TestCreateDomain(mox.MoxTestBase):
  """Tests for privops.domains.createNetwork."""
  def test(self):
    """Test privops.domains.createNetwork.

    With all of the functionality pulled into helper functions,
    createNetwork doesn't actually do all that much work.
    """
    name = 'debmarshal-12'
    memory = '128M'
    disks = ['/home/ebroder/root.img']
    net = 'debmarshal-0'
    mac = '00:11:22:33:44:55'

    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().MultipleTimes().AndReturn(500)
    self.mox.StubOutWithMock(utils, '_acquireLock')
    utils._acquireLock('debmarshal-domlist', fcntl.LOCK_EX)

    self.mox.StubOutWithMock(hypervisors.qemu.QEMU, 'open')
    qemu_con = self.mox.CreateMock(libvirt.virConnect)
    hypervisors.qemu.QEMU.open().AndReturn(qemu_con)

    self.mox.StubOutWithMock(domains, '_validateNetwork')
    domains._validateNetwork(net, qemu_con)

    self.mox.StubOutWithMock(domains, '_validateDisk')
    for d in disks:
      domains._validateDisk(d)

    self.mox.StubOutWithMock(domains, '_findUnusedName')
    domains._findUnusedName(qemu_con).AndReturn(name)

    self.mox.StubOutWithMock(hypervisors.qemu.QEMU, 'domainXMLString')
    hypervisors.qemu.QEMU.domainXMLString(mox.IgnoreArg()).AndReturn(
      '<fake_xml/>')

    self.mox.StubOutWithMock(domains, 'loadDomainState')
    domains.loadDomainState().AndReturn([
      ('debmarshal-1', 500, 'qemu')])

    self.mox.StubOutWithMock(utils, 'storeState')
    utils.storeState([
      ('debmarshal-1', 500, 'qemu'),
      (name, 500, 'qemu')], 'debmarshal-domains')

    self.mox.StubOutWithMock(domains, '_createDomainXML')
    domains._createDomainXML(qemu_con, '<fake_xml/>')

    self.mox.ReplayAll()

    self.assertEqual(privops.Privops().createDomain(
      memory, disks, net, mac, 'qemu'), name)


class TestDestroyDomain(mox.MoxTestBase):
  def setUp(self):
    super(TestDestroyDomain, self).setUp()

    self.domains = [
      ('debmarshal-0', 500, 'qemu'),
      ('debmarshal-1', 501, 'qemu')]

    self.mox.StubOutWithMock(utils, '_acquireLock')
    utils._acquireLock('debmarshal-domlist', fcntl.LOCK_EX)

    self.mox.StubOutWithMock(hypervisors.qemu.QEMU, 'open')
    self.virt_con = self.mox.CreateMock(libvirt.virConnect)
    hypervisors.qemu.QEMU.open().AndReturn(self.virt_con)

    self.mox.StubOutWithMock(domains, 'loadDomainState')
    domains.loadDomainState().AndReturn(self.domains)

  def testNoNetwork(self):
    """Test destroyDomain with a nonexistent domain."""
    self.mox.ReplayAll()

    self.assertRaises(errors.DomainNotFound, privops.Privops().destroyDomain,
                      'debmarshal-3')

  def testNoPermissions(self):
    """Test destroyDomain with a network owned by someone else."""
    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().MultipleTimes().AndReturn(500)

    self.mox.ReplayAll()

    self.assertRaises(errors.AccessDenied, privops.Privops().destroyDomain,
                      'debmarshal-1')

  def testSuccess(self):
    """Test that destroyDomain can succeed."""
    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().MultipleTimes().AndReturn(500)

    virt_dom = self.mox.CreateMock(libvirt.virDomain)
    self.virt_con.lookupByName('debmarshal-0').AndReturn(virt_dom)
    virt_dom.destroy()

    self.mox.StubOutWithMock(utils, 'storeState')
    new_domains = self.domains[1:]
    utils.storeState(new_domains, 'debmarshal-domains')

    self.mox.ReplayAll()

    privops.Privops().destroyDomain('debmarshal-0')


class TestCall(mox.MoxTestBase):
  """Test dispatching privileged operations."""
  def test(self):
    """Test debmarshal.privops.call."""
    self.mox.StubOutWithMock(dbus, 'SystemBus', use_mock_anything=True)
    bus = self.mox.CreateMock(dbus.bus.BusConnection)
    proxy = self.mox.CreateMockAnything()
    method = self.mox.CreateMockAnything()

    dbus.SystemBus().AndReturn(bus)
    bus.get_object(privops.DBUS_BUS_NAME, privops.DBUS_OBJECT_PATH).AndReturn(
      proxy)
    proxy.get_dbus_method(
        'createNetwork', dbus_interface=privops.DBUS_INTERFACE).AndReturn(
        method)
    method(['www.company.com', 'login.company.com'])

    self.mox.ReplayAll()

    privops.call('createNetwork', ['www.company.com', 'login.company.com'])


class TestMain(mox.MoxTestBase):
  """Test the dbus main loop setup."""
  def test(self):
    """Test debmarshal.privops.main.

    Beacuse this is so tied to the system dbus session, which we can't
    even get to as a non-privileged user, we pretty much have to mock
    out everything.
    """
    bus = self.mox.CreateMock(dbus.bus.BusConnection)
    name = self.mox.CreateMock(dbus.service.BusName)
    dbus_obj = self.mox.CreateMock(privops.Privops)
    loop = self.mox.CreateMock(gobject.MainLoop)

    self.mox.StubOutWithMock(dbus.mainloop.glib, 'DBusGMainLoop')
    self.mox.StubOutWithMock(dbus, 'SystemBus', use_mock_anything=True)
    self.mox.StubOutWithMock(dbus.service, 'BusName', use_mock_anything=True)
    self.mox.StubOutWithMock(privops, 'Privops', use_mock_anything=True)
    self.mox.StubOutWithMock(gobject, 'MainLoop', use_mock_anything=True)

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    dbus.SystemBus().AndReturn(bus)
    dbus.service.BusName(privops.DBUS_BUS_NAME, bus).AndReturn(name)
    privops.Privops(name, privops.DBUS_OBJECT_PATH).AndReturn(dbus_obj)
    gobject.MainLoop().AndReturn(loop)
    loop.run()

    self.mox.ReplayAll()

    privops.main()


if __name__ == '__main__':
  unittest.main()
