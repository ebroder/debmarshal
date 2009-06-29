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
    self.assertEqual(privops.main([]), 1)

  def testTooManyArgs(self):
    self.assertEqual(privops.main(['a', 'b', 'c', 'd']), 1)


class TestMain(mox.MoxTestBase):
  """Test argument and return parsing in main"""
  def testSuccess(self):
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
    self.mox.StubOutWithMock(sys, 'stdout')
    print >>sys.stdout, yaml.dump(Exception('failure'))

    self.mox.ReplayAll()

    def test():
      raise Exception('failure')
    privops._subcommands['test'] = test

    self.assertEqual(privops.main([
          'test', yaml.safe_dump([]), yaml.safe_dump({})]), 1)


class TestValidateHostname(mox.MoxTestBase):
  def testInvalidInput(self):
    self.assertRaises(
        errors.InvalidInput,
        (lambda: privops._validateHostname('not-a-domain.faketld')))

  def testValidInput(self):
    # Unfortunately unittest.TestCase doesn't have any built-in
    # mechanisms to mark raised exceptions as a failure instead of an
    # error, but an error seems good enough
    privops._validateHostname('real-hostname.com')


class TestLoadNetworkState(mox.MoxTestBase):
  def setUp(self):
    super(TestLoadNetworkState, self).setUp()

    # We're not going to be testing the lockfile, other than making
    # sure it gets acquired, so we can do all of that here
    self.open = self.mox.CreateMockAnything()
    privops.open = self.open
    self.mox.StubOutWithMock(fcntl, 'lockf')

    lock_file = self.mox.CreateMock(file)
    self.open('/var/lock/debmarshal-networks', 'w+').AndReturn(lock_file)
    fcntl.lockf(lock_file, fcntl.LOCK_SH)

  def tearDown(self):
    del privops.open

  def testNoNetworkFile(self):
    e = IOError(errno.ENOENT, "ENOENT")
    self.open('/var/run/debmarshal-networks').AndRaise(e)

    self.mox.ReplayAll()

    self.assertEqual(privops._loadNetworkState(), [])

  def testExceptionOpeningNetworkFile(self):
    e = IOError(errno.EACCES, "EACCES")
    self.open('/var/run/debmarshal-networks').AndRaise(e)

    self.mox.ReplayAll()

    self.assertRaises(IOError, privops._loadNetworkState)

  def testOpeningLibvirtConnection(self):
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
  def testStoreNetworkState(self):
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
  def testDhcpXml(self):
    name = 'debmarshal-1'
    net = '10.100.4'
    gateway = '%s.1' % net
    netmask = '255.255.255.0'
    hosts = {'wiki.company.com': ('10.100.4.2', 'AA:BB:CC:DD:EE:FF'),
             'login.company.com': ('10.100.4.3', '00:11:22:33:44:55')}

    xml_string = privops._genNetworkXML(name,
                                        gateway,
                                        netmask,
                                        hosts,
                                        True)
    xml = etree.fromstring(xml_string)

    self.assertNotEqual(xml.xpath('/network'), [])

    self.assertNotEqual(xml.xpath('/network/name'), [])
    self.assertEqual(xml.xpath('string(/network/name)'), name)

    self.assertNotEqual(xml.xpath('/network/ip'), [])
    self.assertEqual(xml.xpath('string(/network/ip/@address)'), gateway)
    self.assertEqual(xml.xpath('string(/network/ip/@netmask)'), netmask)

    self.assertNotEqual(xml.xpath('/network/ip/dhcp'), [])

    self.assertNotEqual(xml.xpath('/network/ip/dhcp/range'), [])
    self.assertEqual(xml.xpath('string(/network/ip/dhcp/range/@start)'),
                     '%s.2' % net)
    self.assertEqual(xml.xpath('string(/network/ip/dhcp/range/@end)'),
                     '%s.254' % net)

    self.assertEqual(len(xml.xpath('/network/ip/dhcp/host')), len(hosts))
    for h, hinfo in hosts.iteritems():
      host_node = '/network/ip/dhcp/host[@name = $name]'
      self.assertNotEqual(xml.xpath(host_node, name=h), [])
      self.assertEqual(xml.xpath('string(%s/@ip)' % host_node, name=h), hinfo[0])
      self.assertEqual(xml.xpath('string(%s/@mac)' % host_node, name=h), hinfo[1])


class TestCreateNetwork(mox.MoxTestBase):
  def setUp(self):
    super(TestCreateNetwork, self).setUp()

    self.mox.StubOutWithMock(os, 'geteuid')
    os.geteuid().AndReturn(0)


if __name__ == '__main__':
  unittest.main()
