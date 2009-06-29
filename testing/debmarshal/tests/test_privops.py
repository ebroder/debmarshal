# -*- python-indent: 2; py-indent-offset: 2 -*-
"""tests for the debmarshal setuid support module"""

__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import errno
import fcntl
import os
try:
  import cPickle as pickle
except:
  import pickle
import posix
try:
  import cStringIO as StringIO
except ImportError:
  import StringIO
import subprocess
import sys
import unittest

import mox
import libvirt
from lxml import etree
import virtinst.util
import yaml

from debmarshal import errors
from debmarshal import privops


class TestRunWithPrivilege(mox.MoxTestBase):
  """Testing runWithPrivilege before it actually executes anything"""
  def testFunctionCalledDirectlyAsRoot(self):
    """Test that functions wrapped in runWithPrivilege are executed
    directly if you're already root.
    """
    self.mox.StubOutWithMock(os, 'geteuid')
    os.geteuid().AndReturn(0)

    # We want to make sure that runWithPrivilege doesn't try to
    # re-execute itself through the setuid wrapper.
    #
    # By stubbing out os.stat without actually recording any calls to
    # it, we can trigger an error of runWithPrivilege starts trying to
    # re-execute itself.
    self.mox.StubOutWithMock(os, 'stat')
    self.mox.StubOutWithMock(subprocess, 'Popen')

    self.mox.ReplayAll()

    @privops.runWithPrivilege('test')
    def func():
      # Stupid function - all we care about is that it gets run
      return 1

    self.assertEqual(func(), 1)

  def testAbortIfWrapperNotSetuid(self):
    """Test that if you're not root, and the setuid wrapper isn't
    setuid, runWithPrivileges aborts.
    """
    self.mox.StubOutWithMock(os, 'geteuid')
    os.geteuid().AndReturn(1000)

    self.mox.StubOutWithMock(os, 'stat')
    os.stat(privops._SETUID_BINARY).AndReturn(posix.stat_result([
        # st_mode is the first argument; we don't care about anything
        # else
        0755, 0, 0, 0, 0, 0, 0, 0, 0, 0]))

    self.mox.ReplayAll()

    @privops.runWithPrivilege('test')
    def func():
      self.fail('This function should never have been run.')

    self.assertRaises(errors.Error, func)

class TestReexecResults(mox.MoxTestBase):
  """Test the actual process of execing the setuid wrapper.

  This requires some substantial mocking of both the os module and
  subprocess.Popen.
  """
  def setUp(self):
    """Setup mocks through the point of actually forking and execing.

    This involves faking a binary that's setuid, as well as faking
    actually running it.
    """
    super(TestReexecResults, self).setUp()

    self.mox.StubOutWithMock(os, 'geteuid')
    os.geteuid().AndReturn(1000)

    self.mox.StubOutWithMock(os, 'stat')
    os.stat(privops._SETUID_BINARY).AndReturn(posix.stat_result([
          # st_mode
          04755,
          0, 0, 0,
          # uid
          0,
          0, 0, 0, 0, 0]))

    self.mock_popen = self.mox.CreateMock(subprocess.Popen)
    self.mox.StubOutWithMock(subprocess, 'Popen', use_mock_anything=True)
    subprocess.Popen([privops._SETUID_BINARY,
                      'test',
                      mox.Func(lambda x: yaml.safe_load(x) == ['a', 'b']),
                      mox.Func(lambda x: yaml.safe_load(x) == {'c': 'd'})],
                     stdin=None,
                     stdout=subprocess.PIPE,
                     close_fds=True).AndReturn(self.mock_popen)

  def testReexecSuccessResult(self):
    """Verify that the printout from runWithPrivileges is treated as a
    return value if the program exits with a return code of 0.
    """
    self.mock_popen.wait().AndReturn(0)
    self.mock_popen.stdout = StringIO.StringIO(yaml.dump('foo'))

    self.mox.ReplayAll()

    @privops.runWithPrivilege('test')
    def func(*args, **kwargs):
      return 'foo'

    self.assertEquals(func('a', 'b', c='d'), 'foo')

  def testReexecFailureResult(self):
    """Verify that the printout from runWithPrivileges is treated as
    an exception if the program exits with a return code of 1.
    """
    self.mock_popen.wait().AndReturn(1)
    self.mock_popen.stdout = StringIO.StringIO(yaml.dump(Exception('failure')))

    self.mox.ReplayAll()

    @privops.runWithPrivilege('test')
    def func(*args, **kwargs):
      raise Exception('failure')

    self.assertRaises(Exception, lambda: func('a', 'b', c='d'))


class TestUsage(mox.MoxTestBase):
  """Make sure that usage information gets printed"""
  def setUp(self):
    """Record printing out something that looks like usage information.

    We'll try to trigger it a bunch of different ways.
    """
    super(TestUsage, self).setUp()

    self.mox.StubOutWithMock(sys, 'stderr')
    sys.stderr.write(mox.StrContains('Usage'))
    sys.stderr.write(mox.IgnoreArg()).MultipleTimes()

    self.mox.ReplayAll()

  def testNoArgs(self):
    """Trigger usage information by passing in no arguments"""
    self.assertEqual(privops.main([]), 1)

  def testTooManyArgs(self):
    """Trigger usage information by passing in too many arguments"""
    self.assertEqual(privops.main(['a', 'b', 'c', 'd']), 1)


class TestMain(mox.MoxTestBase):
  """Test argument and return parsing in main"""
  def testSuccess(self):
    """Test that the return value is printed to stdout and that the
    return code is 0 if the function returns
    """
    self.mox.StubOutWithMock(sys, 'stdout')
    print >>sys.stdout, yaml.dump('success')

    self.mox.ReplayAll()

    args = ('foo', {'bar': 'quux'})
    kwargs = {'spam': 'eggs'}

    def test_args(*input_args, **input_kwargs):
      self.assertEqual(args, input_args)
      self.assertEqual(kwargs, input_kwargs)
      return 'success'
    privops._subcommands['test'] = test_args

    self.assertEqual(privops.main([
          'test', yaml.safe_dump(args), yaml.safe_dump(kwargs)]), 0)

  def testFailure(self):
    """Test that the exception is printed to stdout and that the
    return code is 1 if the function raises one
    """
    self.mox.StubOutWithMock(sys, 'stdout')
    print >>sys.stdout, yaml.dump(Exception('failure'))

    self.mox.ReplayAll()

    def test():
      raise Exception('failure')
    privops._subcommands['test'] = test

    self.assertEqual(privops.main([
          'test', yaml.safe_dump([]), yaml.safe_dump({})]), 1)


class TestValidateHostname(mox.MoxTestBase):
  """Test debmarshal.privops._validateHostname"""
  def testInvalidInput(self):
    """Make sure that an exception gets raised if an invalid hostname
    is passed in"""
    self.assertRaises(
        errors.InvalidInput,
        (lambda: privops._validateHostname('not-a-domain.faketld')))

  def testValidInput(self):
    """Test that nothing happens if a valid hostname is passed in"""
    # Unfortunately unittest.TestCase doesn't have any built-in
    # mechanisms to mark raised exceptions as a failure instead of an
    # error, but an error seems good enough
    privops._validateHostname('real-hostname.com')


class TestLoadNetworkState(mox.MoxTestBase):
  """Test loading the network state from /var/run/debmarshal-networks"""
  def setUp(self):
    """The only thing that we can test about the lockfile is that it
    gets acquired, so mock that for all tests."""
    super(TestLoadNetworkState, self).setUp()

    # When run from within a test setUp method, mox.StubOutWithMock
    # doesn't seem to be able to stub out __builtins__, so we'll hack
    # around it ourselves
    self.open = self.mox.CreateMockAnything()
    privops.open = self.open
    self.mox.StubOutWithMock(fcntl, 'lockf')

    lock_file = self.mox.CreateMock(file)
    self.open('/var/lock/debmarshal-networks', 'w+').AndReturn(lock_file)
    fcntl.lockf(lock_file, fcntl.LOCK_SH)

  def tearDown(self):
    """Undo the mock open() function"""
    del privops.open

  def testNoNetworkFile(self):
    """Make sure that the network list is assumed empty if the state
    file doesn't exist"""
    e = IOError(errno.ENOENT,"ENOENT")
    self.open('/var/run/debmarshal-networks').AndRaise(e)

    self.mox.ReplayAll()

    self.assertEqual(privops._loadNetworkState(), [])

  def testExceptionOpeningNetworkFile(self):
    """Make sure that any exception other than ENOENT raised opening
    the state file is re-raised"""
    e = IOError(errno.EACCES, "EACCES")
    self.open('/var/run/debmarshal-networks').AndRaise(e)

    self.mox.ReplayAll()

    self.assertRaises(IOError, privops._loadNetworkState)

  def testOpeningLibvirtConnection(self):
    """Make sure that _loadNetworkState can open its own connection to
    libvirt if needed"""
    networks = StringIO.StringIO(pickle.dumps([]))
    self.open('/var/run/debmarshal-networks').AndReturn(networks)

    self.mox.StubOutWithMock(libvirt, 'open')
    virt_con = self.mox.CreateMock(libvirt.virConnect)
    libvirt.open(mox.IgnoreArg()).AndReturn(virt_con)

    self.mox.StubOutWithMock(libvirt, 'registerErrorHandler')
    libvirt.registerErrorHandler(mox.IgnoreArg(), None)
    libvirt.registerErrorHandler(None, None)

    self.mox.ReplayAll()

    self.assertEqual(privops._loadNetworkState(), [])

  def testNetworkExistenceTest(self):
    """Make sure that networks get dropped from the list in the state
    file if they don't still exist. And that they're kept if they do"""
    networks = StringIO.StringIO(pickle.dumps([('foo', 500, '10.100.1.1'),
                                               ('bar', 501, '10.100.1.2')]))
    self.open('/var/run/debmarshal-networks').AndReturn(networks)

    virt_con = self.mox.CreateMock(libvirt.virConnect)

    self.mox.StubOutWithMock(libvirt, 'registerErrorHandler')
    libvirt.registerErrorHandler(mox.IgnoreArg(), None)

    virt_con.networkLookupByName('foo')
    virt_con.networkLookupByName('bar').AndRaise(libvirt.libvirtError(
        "Network doesn't exist"))

    libvirt.registerErrorHandler(None, None)

    self.mox.ReplayAll()

    self.assertEqual(privops._loadNetworkState(virt_con),
                     [('foo', 500, '10.100.1.1')])


class TestStoreNetworkState(mox.MoxTestBase):
  """Test privops._storeNetworkState"""
  def testStoreNetworkState(self):
    """This is kind of a dumb test. There are no branches or anything
    in _storeNetworkState, and if the code doesn't throw exceptions,
    it's roughly guaranteed to work."""
    networks = [('debmarshal-0', 500, '10.100.1.1')]

    self.open = self.mox.CreateMockAnything()
    privops.open = self.open
    self.mox.StubOutWithMock(fcntl, 'lockf')

    lock_file = self.mox.CreateMock(file)
    self.open('/var/lock/debmarshal-networks', 'w').AndReturn(lock_file)
    fcntl.lockf(lock_file, fcntl.LOCK_EX)

    net_file = self.mox.CreateMock(file)
    self.open('/var/run/debmarshal-networks', 'w').AndReturn(net_file)
    pickle.dump(networks, net_file)

    self.mox.ReplayAll()

    privops._storeNetworkState(networks)

    self.mox.VerifyAll()

    del privops.open


class TestGenNetworkXML(mox.MoxTestBase):
  """Test the XML generated by privops._genNetworkXML"""
  name = 'debmarshal-1'
  net = '10.100.4'
  gateway = '%s.1' % net
  netmask = '255.255.255.0'
  hosts = {'wiki.company.com': ('10.100.4.2', 'AA:BB:CC:DD:EE:FF'),
           'login.company.com': ('10.100.4.3', '00:11:22:33:44:55')}
  def testDhcpXml(self):
    """Test an XML tree with DHCP enabled"""
    xml_string = privops._genNetworkXML(self.name,
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
    xml_string = privops._genNetworkXML(self.name,
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
    _storeNetworkState raises an exception or not, so let's commonize
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
    self.mox.StubOutWithMock(os, 'getuid')
    os.getuid().AndReturn(1000)

    self.mox.StubOutWithMock(privops, '_validateHostname')
    privops._validateHostname(mox.IgnoreArg()).MultipleTimes()

    self.mox.StubOutWithMock(libvirt, 'open')
    virt_con = self.mox.CreateMock(libvirt.virConnect)
    libvirt.open(mox.IgnoreArg()).AndReturn(virt_con)

    self.mox.StubOutWithMock(privops, '_loadNetworkState')
    privops._loadNetworkState(virt_con).AndReturn(self.networks)

    self.mox.StubOutWithMock(virtinst.util, 'randomMAC')
    virtinst.util.randomMAC().MultipleTimes().AndReturn('00:00:00:00:00:00')

    self.mox.StubOutWithMock(privops, '_genNetworkXML')
    privops._genNetworkXML(self.name, self.gateway, '255.255.255.0',
                           self.host_dict, False).AndReturn('<fake_xml />')

    self.virt_net = self.mox.CreateMock(libvirt.virNetwork)
    virt_con.networkDefineXML('<fake_xml />').AndReturn(self.virt_net)
    self.virt_net.create()

  def testStoreSuccess(self):
    """Test createNetwork when everything goes right"""
    self.mox.StubOutWithMock(privops, '_storeNetworkState')
    privops._storeNetworkState(self.networks +
                               [(self.name, 1000, self.gateway)])

    self.mox.ReplayAll()

    self.assertEqual(privops.createNetwork(self.hosts, False),
                     (self.name, self.gateway, '255.255.255.0', self.host_dict))

  def testStoreFailure(self):
    """Test that the network is destroyed if state about it can't be
    stored"""
    self.mox.StubOutWithMock(privops, '_storeNetworkState')
    privops._storeNetworkState(self.networks +
                               [(self.name, 1000, self.gateway)]).\
                               AndRaise(Exception("Error!"))

    self.virt_net.destroy()

    self.mox.ReplayAll()

    self.assertRaises(Exception,
                      (lambda: privops.createNetwork(self.hosts, False)))


if __name__ == '__main__':
  unittest.main()
