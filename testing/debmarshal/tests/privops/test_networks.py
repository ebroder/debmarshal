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
"""tests for the debmarshal privileged networking module"""


__authors__ = [
  'Evan Broder <ebroder@google.com>',
]


import fcntl
import os
try:
  import cPickle as pickle
except ImportError:
  import pickle
import unittest

import mox
import libvirt
from lxml import etree
import virtinst.util

from debmarshal import errors
from debmarshal.privops import networks
from debmarshal.privops import utils


class TestValidateHostname(mox.MoxTestBase):
  """Test debmarshal.privops.networks._validateHostname"""
  def testInvalidInput(self):
    """Make sure that an exception gets raised if an invalid hostname
    is passed in"""
    self.assertRaises(
        errors.InvalidInput,
        (lambda: networks._validateHostname('not-a-domain.faketld')))

  def testValidInput(self):
    """Test that nothing happens if a valid hostname is passed in"""
    # Unfortunately unittest.TestCase doesn't have any built-in
    # mechanisms to mark raised exceptions as a failure instead of an
    # error, but an error seems good enough
    networks._validateHostname('real-hostname.com')


class TestLoadNetworkState(mox.MoxTestBase):
  """Test loading the network state from /var/run/debmarshal-networks"""
  def testOpeningLibvirtConnection(self):
    """Make sure that loadNetworkState can open its own connection to
    libvirt if needed"""
    self.mox.StubOutWithMock(utils, 'loadState')
    utils.loadState('debmarshal-networks').AndReturn(None)

    self.mox.StubOutWithMock(libvirt, 'open')
    virt_con = self.mox.CreateMock(libvirt.virConnect)
    libvirt.open(mox.IgnoreArg()).AndReturn(virt_con)

    self.mox.StubOutWithMock(libvirt, 'registerErrorHandler')
    libvirt.registerErrorHandler(mox.IgnoreArg(), None)
    libvirt.registerErrorHandler(None, None)

    self.mox.ReplayAll()

    self.assertEqual(networks.loadNetworkState(), [])

  def testNetworkExistenceTest(self):
    """Make sure that networks get dropped from the list in the state
    file if they don't still exist. And that they're kept if they do"""
    self.mox.StubOutWithMock(utils, 'loadState')
    utils.loadState('debmarshal-networks').AndReturn(
      [('foo', 500, '10.100.1.1'),
       ('bar', 501, '10.100.1.2')])

    virt_con = self.mox.CreateMock(libvirt.virConnect)

    self.mox.StubOutWithMock(libvirt, 'registerErrorHandler')
    libvirt.registerErrorHandler(mox.IgnoreArg(), None)

    virt_con.networkLookupByName('foo')
    virt_con.networkLookupByName('bar').AndRaise(libvirt.libvirtError(
        "Network doesn't exist"))

    libvirt.registerErrorHandler(None, None)

    self.mox.ReplayAll()

    self.assertEqual(networks.loadNetworkState(virt_con),
                     [('foo', 500, '10.100.1.1')])

  def testTwoBadNetworks(self):
    """Test finding two nonexistent networks when loading state."""
    nets = [('foo', 500, '10.100.1.1'),
            ('bar', 500, '10.100.2.1'),
            ('baz', 500, '10.100.3.1'),
            ('quux', 500, '10.100.4.1'),
            ('spam', 500, '10.100.5.1'),
            ('eggs', 500, '10.100.6.1')]

    self.mox.StubOutWithMock(utils, 'loadState')
    utils.loadState('debmarshal-networks').AndReturn(nets[:])

    virt_con = self.mox.CreateMock(libvirt.virConnect)

    self.mox.StubOutWithMock(libvirt, 'registerErrorHandler')

    libvirt.registerErrorHandler(mox.IgnoreArg(), None)

    virt_con.networkLookupByName('foo')
    virt_con.networkLookupByName('bar')
    virt_con.networkLookupByName('baz').AndRaise(libvirt.libvirtError(
        "Network doens't exist"))
    virt_con.networkLookupByName('quux')
    virt_con.networkLookupByName('spam').AndRaise(libvirt.libvirtError(
        "Network doesn't exist"))
    virt_con.networkLookupByName('eggs')

    libvirt.registerErrorHandler(None, None)

    self.mox.ReplayAll()

    self.assertEqual(networks.loadNetworkState(virt_con),
                     [nets[0], nets[1], nets[3], nets[5]])


class TestNetworkBounds(mox.MoxTestBase):
  """Test converting a gateway/netmask to the low and high IP
  addresses in the network"""
  def test24(self):
    """Test a converting a /24 network, what debmarshal uses"""
    self.assertEqual(networks._networkBounds('192.168.1.1', '255.255.255.0'),
                     ('192.168.1.2', '192.168.1.254'))


class TestGenNetworkXML(mox.MoxTestBase):
  """Test the XML generated by networks._genNetworkXML"""
  name = 'debmarshal-1'
  net = '10.100.4'
  gateway = '%s.1' % net
  netmask = '255.255.255.0'
  hosts = {'wiki.company.com': ('10.100.4.2', 'AA:BB:CC:DD:EE:FF'),
           'login.company.com': ('10.100.4.3', '00:11:22:33:44:55')}

  def testDhcpXml(self):
    """Test an XML tree with DHCP enabled"""
    xml_string = networks._genNetworkXML(self.name,
                                        self.gateway,
                                        self.netmask,
                                        self.hosts,
                                        True)
    xml = etree.fromstring(xml_string)

    # These assertions are simply used to test that the element with
    # the right name exists
    self.assertNotEqual(xml.xpath('/network'), [])

    self.assertNotEqual(xml.xpath('/network/name'), [])
    self.assertEqual(xml.xpath('string(/network/name)'), self.name)

    self.assertNotEqual(xml.xpath('/network/ip'), [])
    self.assertEqual(xml.xpath('string(/network/ip/@address)'), self.gateway)
    self.assertEqual(xml.xpath('string(/network/ip/@netmask)'), self.netmask)

    self.assertNotEqual(xml.xpath('/network/ip/dhcp'), [])

    self.assertNotEqual(xml.xpath('/network/ip/dhcp/range'), [])
    self.assertEqual(xml.xpath('string(/network/ip/dhcp/range/@start)'),
                     '%s.2' % self.net)
    self.assertEqual(xml.xpath('string(/network/ip/dhcp/range/@end)'),
                     '%s.254' % self.net)

    self.assertEqual(len(xml.xpath('/network/ip/dhcp/host')), len(self.hosts))
    for h, hinfo in self.hosts.iteritems():
      host_node = '/network/ip/dhcp/host[@name = $name]'
      self.assertNotEqual(xml.xpath(host_node, name=h), [])
      self.assertEqual(xml.xpath('string(%s/@ip)' % host_node, name=h), hinfo[0])
      self.assertEqual(xml.xpath('string(%s/@mac)' % host_node, name=h), hinfo[1])

  def testNoDhcpXML(self):
    """Test an XML without DHCP enabled"""
    xml_string = networks._genNetworkXML(self.name,
                                        self.gateway,
                                        self.netmask,
                                        self.hosts,
                                        False)
    xml = etree.fromstring(xml_string)

    self.assertNotEqual(xml.xpath('/network'), [])

    self.assertNotEqual(xml.xpath('/network/name'), [])
    self.assertEqual(xml.xpath('string(/network/name)'), self.name)

    self.assertNotEqual(xml.xpath('/network/ip'), [])
    self.assertEqual(xml.xpath('string(/network/ip/@address)'), self.gateway)
    self.assertEqual(xml.xpath('string(/network/ip/@netmask)'), self.netmask)

    self.assertEqual(xml.xpath('/network/ip/*'), [])


class TestCreateNetwork(mox.MoxTestBase):
  """Now that we've tested the pieces that make up createNetwork,
  let's test createNetwork itself"""
  def setUp(self):
    """The only two interesting conditions to test here are whether
    storeState raises an exception or not, so let's commonize
    everything else"""
    super(TestCreateNetwork, self).setUp()

    self.networks = [('debmarshal-0', 500, '10.100.0.1'),
                     ('debmarshal-3', 500, '10.100.1.1'),
                     ('debmarshal-4', 500, '10.100.2.1'),
                     ('debmarshal-4', 500, '10.100.5.1')]
    self.name = 'debmarshal-1'
    self.gateway = '10.100.3.1'
    self.hosts = ['wiki.company.com', 'login.company.com']
    self.host_dict = {'wiki.company.com':
                      ('10.100.3.2', '00:00:00:00:00:00'),
                      'login.company.com':
                      ('10.100.3.3', '00:00:00:00:00:00')}

    self.mox.StubOutWithMock(os, 'geteuid')
    os.geteuid().AndReturn(0)
    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().AndReturn(1000)

    self.mox.StubOutWithMock(utils, '_acquireLock')
    utils._acquireLock('debmarshal-netlist', fcntl.LOCK_EX)

    self.mox.StubOutWithMock(networks, '_validateHostname')
    networks._validateHostname(mox.IgnoreArg()).MultipleTimes()

    self.mox.StubOutWithMock(libvirt, 'open')
    virt_con = self.mox.CreateMock(libvirt.virConnect)
    libvirt.open(mox.IgnoreArg()).AndReturn(virt_con)

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
                     [(self.name, 1000, self.gateway)],
                     'debmarshal-networks')

    self.mox.ReplayAll()

    self.assertEqual(networks.createNetwork(self.hosts, False),
                     (self.name, self.gateway, '255.255.255.0', self.host_dict))

  def testStoreFailure(self):
    """Test that the network is destroyed if state about it can't be
    stored"""
    self.mox.StubOutWithMock(utils, 'storeState')
    utils.storeState(self.networks +
                     [(self.name, 1000, self.gateway)],
                     'debmarshal-networks').\
                     AndRaise(Exception("Error!"))

    self.virt_net.destroy()
    self.virt_net.undefine()

    self.mox.ReplayAll()

    self.assertRaises(Exception,
                      (lambda: networks.createNetwork(self.hosts, False)))


class TestDestroyNetwork(mox.MoxTestBase):
  def setUp(self):
    """Setup some mocks common to all tests of destroyNetwork"""
    super(TestDestroyNetwork, self).setUp()

    self.mox.StubOutWithMock(os, 'geteuid')
    os.geteuid().MultipleTimes().AndReturn(0)

    self.mox.StubOutWithMock(utils, '_acquireLock')
    utils._acquireLock('debmarshal-netlist', fcntl.LOCK_EX)

    self.mox.StubOutWithMock(libvirt, 'open')
    self.virt_con = self.mox.CreateMock(libvirt.virConnect)
    libvirt.open(mox.IgnoreArg()).AndReturn(self.virt_con)

    self.networks = [('debmarshal-0', 501, '10.100.0.1'),
                     ('debmarshal-1', 500, '10.100.1.1')]
    self.mox.StubOutWithMock(networks, 'loadNetworkState')
    networks.loadNetworkState(self.virt_con).AndReturn(self.networks)

  def testNoNetwork(self):
    """Test that destroyNetwork doesn't try to delete a network it
    doesn't know about"""
    self.mox.ReplayAll()

    self.assertRaises(errors.NetworkNotFound,
                      (lambda: networks.destroyNetwork('debmarshal-3')))

  def testNoPermissions(self):
    """Test that destroyNetwork refuses to delete a network if you
    don't own it"""
    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().MultipleTimes().AndReturn(501)

    self.mox.ReplayAll()

    self.assertRaises(errors.AccessDenied,
                      (lambda: networks.destroyNetwork('debmarshal-1')))

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

    networks.destroyNetwork('debmarshal-0')


if __name__ == '__main__':
  unittest.main()
