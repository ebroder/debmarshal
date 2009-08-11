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
import traceback
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
import debmarshal.utils
from debmarshal._privops import domains
from debmarshal._privops import networks
from debmarshal._privops import utils


class TestCoerceDbusArgs(unittest.TestCase):
  """Test debmarshal.privops._coerceDbusArgs."""
  def test(self):

    @privops._coerceDbusArgs
    def func(a):
      self.assert_(type(a) is int)
      return True

    self.assertEqual(func(dbus.Int16(12)), True)


class TestDaemonize(mox.MoxTestBase):
  def setUp(self):
    super(TestDaemonize, self).setUp()

    self.mox.StubOutWithMock(os, 'fork')
    self.mox.StubOutWithMock(os, 'setsid')
    self.mox.StubOutWithMock(os, 'close')
    self.mox.StubOutWithMock(os, 'open')
    self.mox.StubOutWithMock(os, 'dup2')

  def testParent(self):
    os.fork().AndReturn(1234)

    self.mox.ReplayAll()

    self.assertEqual(privops._daemonize(), False)

  def testIntermediate(self):
    os.fork().AndReturn(0)
    os.setsid()
    os.fork().AndReturn(1234)

    self.mox.ReplayAll()

    self.assertRaises(SystemExit, privops._daemonize)

  def testDaemon(self):
    os.fork().AndReturn(0)
    os.setsid()
    os.fork().AndReturn(0)

    os.close(0)
    os.close(1)
    os.close(2)

    os.open('/dev/null', os.O_RDWR)
    os.dup2(0, 1)
    os.dup2(0, 2)

    self.mox.ReplayAll()

    self.assertEqual(privops._daemonize(), True)


class TestAsyncCallBase(mox.MoxTestBase):
  def setUp(self):
    super(TestAsyncCallBase, self).setUp()

    self.mox.StubOutWithMock(privops, '_daemonize')


class TestAsyncCallNotDaemon(TestAsyncCallBase):
  def testNotDaemon(self):
    privops._daemonize().AndReturn(False)

    @privops._asyncCall
    def shouldNotBeCalled(_debmarshal_sender=None):
      raise Exception("This function should not be called")

    self.mox.ReplayAll()

    shouldNotBeCalled(':1.13')


class TestAsyncCallDaemon(TestAsyncCallBase):
  def setUp(self):
    super(TestAsyncCallDaemon, self).setUp()

    self.sender = ':1.13'

    privops._daemonize().AndReturn(True)

    self.mox.StubOutWithMock(dbus, 'SystemBus', use_mock_anything=True)

    bus = self.mox.CreateMock(dbus.bus.BusConnection)
    self.proxy = self.mox.CreateMockAnything()

    dbus.SystemBus().AndReturn(bus)
    bus.get_object(self.sender, privops.DBUS_WAIT_OBJECT_PATH).AndReturn(
      self.proxy)

  def testSuccess(self):
    @privops._asyncCall
    def successFunc(_debmarshal_sender=None):
      pass

    self.proxy.callReturn(dbus_interface=privops.DBUS_WAIT_INTERFACE)

    self.mox.ReplayAll()

    self.assertRaises(SystemExit, successFunc, self.sender)

  def testFailure(self):
    self.mox.StubOutWithMock(traceback, 'format_exc')

    traceback.format_exc().AndReturn('A traceback!')

    @privops._asyncCall
    def failFunc(_debmarshal_sender=None):
      raise Exception('Failure!')

    self.proxy.callError('A traceback!',
                         dbus_interface=privops.DBUS_WAIT_INTERFACE)

    self.mox.ReplayAll()

    self.assertRaises(SystemExit, failFunc, self.sender)


class TestCreateNetwork(mox.MoxTestBase):
  """Test debmarshal.privops.createNetwork."""
  def setUp(self):
    """The only two interesting conditions to test here are whether
    storeState raises an exception or not, so let's commonize
    everything else"""
    super(TestCreateNetwork, self).setUp()

    self.networks = {'debmarshal-0': 500,
                     'debmarshal-3': 500,
                     'debmarshal-4': 500,
                     'debmarshal-4': 500}
    self.name = 'debmarshal-1'
    self.gateway = '169.254.3.1'
    self.hosts = ['wiki.company.com', 'login.company.com']
    self.host_dict = {'wiki.company.com':
                      ('169.254.3.2', '00:00:00:00:00:00'),
                      'login.company.com':
                      ('169.254.3.3', '00:00:00:00:00:00')}

    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().AndReturn(1000)

    self.mox.StubOutWithMock(debmarshal.utils, 'acquireLock')
    debmarshal.utils.acquireLock('debmarshal-netlist', fcntl.LOCK_EX)

    self.mox.StubOutWithMock(networks, '_validateHostname')
    networks._validateHostname(mox.IgnoreArg()).MultipleTimes()

    self.mox.StubOutWithMock(libvirt, 'open')
    self.virt_con = self.mox.CreateMock(libvirt.virConnect)
    libvirt.open(mox.IgnoreArg()).AndReturn(self.virt_con)

    self.mox.StubOutWithMock(networks, '_findUnusedName')
    networks._findUnusedName(self.virt_con).AndReturn(self.name)

    self.mox.StubOutWithMock(networks, '_findUnusedNetwork')
    networks._findUnusedNetwork(self.virt_con, len(self.hosts)).\
        AndReturn((self.gateway, '255.255.255.0'))

    self.mox.StubOutWithMock(networks, 'loadNetworkState')
    networks.loadNetworkState(self.virt_con).AndReturn(dict(self.networks))

    self.mox.StubOutWithMock(virtinst.util, 'randomMAC')
    virtinst.util.randomMAC().MultipleTimes().AndReturn('00:00:00:00:00:00')

    self.mox.StubOutWithMock(networks, '_genNetworkXML')
    networks._genNetworkXML(self.name, self.gateway, '255.255.255.0',
                           self.host_dict).AndReturn('<fake_xml />')

    self.virt_net = self.mox.CreateMock(libvirt.virNetwork)
    self.virt_con.networkDefineXML('<fake_xml />').AndReturn(self.virt_net)
    self.virt_net.create()

  def testStoreSuccess(self):
    """Test createNetwork when everything goes right"""
    self.mox.StubOutWithMock(utils, 'storeState')
    self.networks[self.name] = 1000
    utils.storeState(self.networks, 'debmarshal-networks')

    self.mox.ReplayAll()

    self.assertEqual(privops.Privops().createNetwork(self.hosts),
                     (self.name, self.gateway, '255.255.255.0', self.host_dict))

  def testStoreFailure(self):
    """Test that the network is destroyed if state about it can't be
    stored"""
    self.mox.StubOutWithMock(utils, 'storeState')
    self.networks[self.name] = 1000
    utils.storeState(self.networks, 'debmarshal-networks').\
                     AndRaise(Exception("Error!"))

    self.virt_con.networkLookupByName(self.name).MultipleTimes().AndReturn(
        self.virt_net)
    self.virt_net.destroy()
    self.virt_net.undefine()

    self.mox.ReplayAll()

    self.assertRaises(Exception, privops.Privops().createNetwork,
                      self.hosts)


class TestDestroyNetwork(mox.MoxTestBase):
  def setUp(self):
    """Setup some mocks common to all tests of destroyNetwork"""
    super(TestDestroyNetwork, self).setUp()

    self.mox.StubOutWithMock(debmarshal.utils, 'acquireLock')
    debmarshal.utils.acquireLock('debmarshal-netlist', fcntl.LOCK_EX)

    self.mox.StubOutWithMock(libvirt, 'open')
    self.virt_con = self.mox.CreateMock(libvirt.virConnect)
    libvirt.open(mox.IgnoreArg()).AndReturn(self.virt_con)

    self.networks = {'debmarshal-0': 501,
                     'debmarshal-1': 500}
    self.mox.StubOutWithMock(networks, 'loadNetworkState')
    networks.loadNetworkState(self.virt_con).AndReturn(dict(self.networks))

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
    self.virt_con.networkLookupByName('debmarshal-0').MultipleTimes().AndReturn(
        virt_net)
    virt_net.destroy()
    virt_net.undefine()

    self.mox.StubOutWithMock(utils, 'storeState')
    del self.networks['debmarshal-0']
    utils.storeState(self.networks, 'debmarshal-networks')

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
    self.mox.StubOutWithMock(debmarshal.utils, 'acquireLock')
    debmarshal.utils.acquireLock('debmarshal-domlist', fcntl.LOCK_EX)

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
    domains.loadDomainState().AndReturn({
        ('debmarshal-1', 'qemu'): 500})

    self.mox.StubOutWithMock(utils, 'storeState')
    utils.storeState({
      ('debmarshal-1', 'qemu'): 500,
      (name, 'qemu'): 500}, 'debmarshal-domains')

    qemu_con.createLinux('<fake_xml/>', 0)

    self.mox.ReplayAll()

    self.assertEqual(privops.Privops().createDomain(
      memory, disks, net, mac, 'qemu', 'x86_64'), name)


class TestDestroyDomain(mox.MoxTestBase):
  def setUp(self):
    super(TestDestroyDomain, self).setUp()

    self.domains = {
        ('debmarshal-0', 'qemu'): 500,
        ('debmarshal-1', 'qemu'): 501}

    self.mox.StubOutWithMock(debmarshal.utils, 'acquireLock')
    debmarshal.utils.acquireLock('debmarshal-domlist', fcntl.LOCK_EX)

    self.mox.StubOutWithMock(hypervisors.qemu.QEMU, 'open')
    self.virt_con = self.mox.CreateMock(libvirt.virConnect)
    hypervisors.qemu.QEMU.open().AndReturn(self.virt_con)

    self.mox.StubOutWithMock(domains, 'loadDomainState')
    domains.loadDomainState().AndReturn(dict(self.domains))

  def testNoNetwork(self):
    """Test destroyDomain with a nonexistent domain."""
    self.mox.ReplayAll()

    self.assertRaises(errors.DomainNotFound, privops.Privops().destroyDomain,
                      'debmarshal-3', 'qemu')

  def testNoPermissions(self):
    """Test destroyDomain with a network owned by someone else."""
    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().MultipleTimes().AndReturn(500)

    self.mox.ReplayAll()

    self.assertRaises(errors.AccessDenied, privops.Privops().destroyDomain,
                      'debmarshal-1', 'qemu')

  def testSuccess(self):
    """Test that destroyDomain can succeed."""
    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().MultipleTimes().AndReturn(500)

    virt_dom = self.mox.CreateMock(libvirt.virDomain)
    self.virt_con.lookupByName('debmarshal-0').AndReturn(virt_dom)
    virt_dom.destroy()

    self.mox.StubOutWithMock(utils, 'storeState')
    del self.domains[('debmarshal-0', 'qemu')]
    utils.storeState(self.domains, 'debmarshal-domains')

    self.mox.ReplayAll()

    privops.Privops().destroyDomain('debmarshal-0', 'qemu')


class TestCallback(mox.MoxTestBase):
  def test(self):
    loop = self.mox.CreateMock(gobject.MainLoop)

    self.mox.StubOutWithMock(gobject, 'idle_add')

    cb = privops.Callback()
    cb._loop = loop
    cb._error = None

    gobject.idle_add(loop.quit)
    gobject.idle_add(loop.quit)

    self.mox.ReplayAll()

    cb.callReturn()

    self.assertEqual(cb._error, None)

    error_val = 'Look! An error!'
    cb.callError(error_val)

    self.assertEqual(cb._error, error_val)


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


class TestCallWait(mox.MoxTestBase):
  def setUp(self):
    super(TestCallWait, self).setUp()

    bus = self.mox.CreateMock(dbus.bus.BusConnection)
    self.call = self.mox.CreateMock(privops.Callback)
    self.loop = self.mox.CreateMock(gobject.MainLoop)

    self.mox.StubOutWithMock(privops, 'call')
    self.mox.StubOutWithMock(dbus.mainloop.glib, 'DBusGMainLoop')
    self.mox.StubOutWithMock(dbus, 'SystemBus', use_mock_anything=True)
    self.mox.StubOutWithMock(privops, 'Callback', use_mock_anything=True)
    self.mox.StubOutWithMock(gobject, 'MainLoop', use_mock_anything=True)

    self.method = 'generateImage'
    self.args = (None, None)

    privops.call(self.method, *self.args)

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    dbus.SystemBus().AndReturn(bus)

    privops._callback = None
    privops.Callback(bus, privops.DBUS_WAIT_OBJECT_PATH).AndReturn(self.call)
    gobject.MainLoop().AndReturn(self.loop)

  def testSuccess(self):
    def _runSideEffects():
      self.call._error = None

    self.loop.run().WithSideEffects(_runSideEffects)

    self.mox.ReplayAll()

    privops.callWait(self.method, *self.args)

  def testFailure(self):
    def _runSideEffects():
      self.call._error = Exception('This is an error!')

    self.loop.run().WithSideEffects(_runSideEffects)

    self.mox.ReplayAll()

    self.assertRaises(Exception, privops.callWait, self.method, *self.args)


class TestMaybeExit(mox.MoxTestBase):
  """Test exiting from the main loop."""
  def test(self):
    """Test debmarshal.privops._maybeExit."""
    loop = self.mox.CreateMockAnything()
    loop.quit()

    self.mox.ReplayAll()

    self.assertEqual(privops._maybeExit(loop), True)
    self.assertEqual(privops._READY_TO_EXIT, True)
    privops._READY_TO_EXIT = False
    self.assertEqual(privops._maybeExit(loop), True)
    self.assertEqual(privops._READY_TO_EXIT, True)
    privops._maybeExit(loop)


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
    self.mox.StubOutWithMock(gobject, 'timeout_add_seconds')

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    dbus.SystemBus().AndReturn(bus)
    dbus.service.BusName(privops.DBUS_BUS_NAME, bus).AndReturn(name)
    privops.Privops(name, privops.DBUS_OBJECT_PATH).AndReturn(dbus_obj)
    gobject.MainLoop().AndReturn(loop)
    gobject.timeout_add_seconds(1, privops._maybeExit, loop)
    loop.run()

    self.mox.ReplayAll()

    privops.main()


if __name__ == '__main__':
  unittest.main()
