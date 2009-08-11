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
"""tests for debmarshal.distros.base."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import ConfigParser
import glob
try:
  import hashlib as md5
except ImportError:
  import md5
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

import mox
import pkg_resources

from debmarshal.distros import base
from debmarshal import errors


class NoDefaultsDistribution(base.Distribution):
  """A test distribution class.

  This class doesn't hit the filesystem for defaults, so any testing
  against a Distribution subclass should use this."""
  def _updateDefaults(self):
    pass


class TestCaptureCall(mox.MoxTestBase):
  def testPassStdin(self):
    mock_p = self.mox.CreateMock(subprocess.Popen)
    self.mox.StubOutWithMock(subprocess, 'Popen', use_mock_anything=True)

    subprocess.Popen(['ls'],
                     stdin='foo',
                     stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT).AndReturn(
        mock_p)
    mock_p.communicate(None).AndReturn(('bar', 'baz'))
    mock_p.returncode = 0

    self.mox.ReplayAll()

    self.assertEqual(base.captureCall(['ls'], stdin='foo'),
                     'bar')

  def testPassStdout(self):
    mock_p = self.mox.CreateMock(subprocess.Popen)
    self.mox.StubOutWithMock(subprocess, 'Popen', use_mock_anything=True)

    subprocess.Popen(['ls'],
                     stdin=subprocess.PIPE,
                     stdout='blah',
                     stderr=subprocess.STDOUT).AndReturn(
        mock_p)
    mock_p.communicate(None).AndReturn((None, None))
    mock_p.returncode = 0

    self.mox.ReplayAll()

    self.assertEqual(base.captureCall(['ls'], stdout='blah'),
                     None)

  def testPassStderr(self):
    mock_p = self.mox.CreateMock(subprocess.Popen)
    self.mox.StubOutWithMock(subprocess, 'Popen', use_mock_anything=True)

    subprocess.Popen(['ls'],
                     stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE,
                     stderr='foo').AndReturn(
        mock_p)
    mock_p.communicate(None).AndReturn(('bar', 'baz'))
    mock_p.returncode = 0

    self.mox.ReplayAll()

    self.assertEqual(base.captureCall(['ls'], stderr='foo'),
                     'bar')

  def testError(self):
    mock_p = self.mox.CreateMock(subprocess.Popen)
    self.mox.StubOutWithMock(subprocess, 'Popen', use_mock_anything=True)

    subprocess.Popen(['ls'],
                     stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT).AndReturn(
        mock_p)
    mock_p.communicate(None).AndReturn((None, None))
    mock_p.returncode = 255

    self.mox.ReplayAll()

    self.assertRaises(subprocess.CalledProcessError, base.captureCall, ['ls'])


class TestCreateNewLoopDev(mox.MoxTestBase):
  def testSuccess(self):
    self.mox.StubOutWithMock(glob, 'glob')
    self.mox.StubOutWithMock(os, 'mknod')

    glob.glob('/dev/loop*').AndReturn(['/dev/loop%d' % i for i in xrange(8)])
    os.mknod('/dev/loop8', stat.S_IFBLK | 0600, os.makedev(7, 8)).AndRaise(
      OSError(17, 'File exists'))

    glob.glob('/dev/loop*').AndReturn(['/dev/loop%d' % i for i in xrange(9)])
    os.mknod('/dev/loop9', stat.S_IFBLK | 0600, os.makedev(7, 9))

    self.mox.ReplayAll()

    base._createNewLoopDev()

  def testFailure(self):
    self.mox.StubOutWithMock(glob, 'glob')
    self.mox.StubOutWithMock(os, 'mknod')

    glob.glob('/dev/loop*').AndReturn(['/dev/loop0'])
    os.mknod('/dev/loop1', stat.S_IFBLK | 0600, os.makedev(7, 1)).AndRaise(
      OSError(13, 'Permission denied'))

    self.mox.ReplayAll()

    self.assertRaises(OSError,
                      base._createNewLoopDev)


class TestLoop(mox.MoxTestBase):
  def testSetup(self):
    self.mox.StubOutWithMock(base, 'captureCall')

    base.captureCall(['losetup', '--show', '--find', 'foo']).AndReturn(
        "/dev/loop0\n")

    self.mox.ReplayAll()

    self.assertEqual(base.setupLoop('foo'), '/dev/loop0')

  def testSetupError(self):
    self.mox.StubOutWithMock(base, 'captureCall')

    base.captureCall(['losetup', '--show', '--find', 'foo']).\
        MultipleTimes().\
        AndRaise(errors.CalledProcessError(
          255,
          ['losetup'],
          'losetup: could not find any free loop device\n'))

    self.mox.StubOutWithMock(base, '_createNewLoopDev')
    base._createNewLoopDev().MultipleTimes()

    self.mox.ReplayAll()

    self.assertRaises(errors.CalledProcessError,
                      base.setupLoop,
                      'foo')

  def testCleanup(self):
    self.mox.StubOutWithMock(base, 'captureCall')

    base.captureCall(['losetup', '-d', '/dev/loop0'])

    self.mox.ReplayAll()

    base.cleanupLoop('/dev/loop0')


class TestCreateSparseFile(unittest.TestCase):
  """Test creating sparse files.

  For once, this has well enough defined behavior that we can actually
  test ends instead of means.
  """
  def testCreateFile(self):
    fd, name = tempfile.mkstemp()
    os.close(fd)
    size = 1024 ** 2

    base.createSparseFile(name, size)

    try:
      self.assertEqual(os.stat(name).st_size, size)
      self.assertEqual(os.stat(name).st_blocks, 0)
    finally:
      os.remove(name)

  def testCreateDirectoriesAndFile(self):
    dir = tempfile.mkdtemp()

    name = os.path.join(dir, 'foo/file')
    size = 1024 ** 2
    base.createSparseFile(name, size)

    try:
      self.assertEqual(os.stat(name).st_size, size)
      self.assertEqual(os.stat(name).st_blocks, 0)
    finally:
      shutil.rmtree(dir)


class TestRandomString(unittest.TestCase):
  def test(self):
    # This is going to fail once in a gajillion years, and it'll be
    # hilarious, but you can't really do any more thorough testing
    # without knowledge of the internals, which I'd just as soon not
    # assume.
    self.assertNotEqual(base._randomString(),
                        base._randomString())


class TestCreateCow(mox.MoxTestBase):
  def setUp(self):
    super(TestCreateCow, self).setUp()

    self.mox.StubOutWithMock(tempfile, 'mkdtemp')
    self.mox.StubOutWithMock(base, 'captureCall')
    self.mox.StubOutWithMock(base, 'createSparseFile')
    self.mox.StubOutWithMock(base, 'setupLoop')
    self.mox.StubOutWithMock(base, '_randomString')
    self.mox.StubOutWithMock(base, 'cleanupLoop')
    self.mox.StubOutWithMock(shutil, 'rmtree')

    tempfile.mkdtemp().AndReturn('/tmp/tmpcowmount')

    base.captureCall(['mount',
                      '-t', 'tmpfs',
                      '-o', 'size=1024',
                      'tmpcow',
                      '/tmp/tmpcowmount'])
    base.createSparseFile('/tmp/tmpcowmount/cowfile', 1024)
    base.setupLoop('/tmp/tmpcowmount/cowfile').AndReturn('/dev/loop1')
    base.captureCall(['blockdev', '--getsz', '/dev/loop0']).AndReturn('4096\n')

  def testSuccess(self):
    base._randomString().AndReturn('existsalready')
    base.captureCall(['dmsetup', 'create', 'existsalready'],
                stdin_str=mox.IgnoreArg()).AndRaise(
      errors.CalledProcessError(
        255,
        ['dmsetup'],
        'device-mapper: create ioctl failed: Device or resource busy\n'))

    base._randomString().AndReturn('doesntexist')
    base.captureCall(['dmsetup', 'create', 'doesntexist'],
                stdin_str=mox.IgnoreArg())

    base.captureCall(['umount', '-l', '/tmp/tmpcowmount'])
    shutil.rmtree('/tmp/tmpcowmount')

    self.mox.ReplayAll()

    self.assertEquals(base.createCow('/dev/loop0', 1024),
                      '/dev/mapper/doesntexist')

  def testFailure(self):
    base._randomString().AndReturn('herebedragons')
    base.captureCall(['dmsetup', 'create', 'herebedragons'],
                stdin_str=mox.IgnoreArg()).AndRaise(
      errors.CalledProcessError(
        255,
        ['dmsetup'],
        'And now for something completely different!\n'))

    base.cleanupLoop('/dev/loop1')

    base.captureCall(['umount', '-l', '/tmp/tmpcowmount'])
    shutil.rmtree('/tmp/tmpcowmount')

    self.mox.ReplayAll()

    self.assertRaises(errors.CalledProcessError,
                      base.createCow,
                      '/dev/loop0',
                      1024)


class TestCleanupCow(mox.MoxTestBase):
  def setUp(self):
    super(TestCleanupCow, self).setUp()

    self.mox.StubOutWithMock(base, 'captureCall')
    self.mox.StubOutWithMock(base, 'cleanupLoop')

  def testSuccess(self):
    base.captureCall(['dmsetup', 'table', '/dev/mapper/abcd']).AndReturn(
      '0 1024 snapshot 7:0 7:1 128')

    base.captureCall(['dmsetup', 'remove', '/dev/mapper/abcd'])
    base.cleanupLoop('/dev/loop1')

    self.mox.ReplayAll()

    base.cleanupCow('/dev/mapper/abcd')

  def testError(self):
    base.captureCall(['dmsetup', 'table', '/dev/mapper/abcd']).AndReturn(
      '0 1024 snapshot 7:0 8:1 128')

    self.mox.ReplayAll()

    self.assertRaises(Exception,
                      base.cleanupCow,
                      '/dev/mapper/abcd')


class TestFindDistribution(mox.MoxTestBase):
  def test(self):
    entry_point = self.mox.CreateMock(pkg_resources.EntryPoint)

    self.mox.StubOutWithMock(pkg_resources, 'iter_entry_points')
    pkg_resources.iter_entry_points(
      'debmarshal.distributions',
      name='base').AndReturn(
      (x for x in [entry_point]))

    entry_point.load().AndReturn(base.Distribution)

    self.mox.ReplayAll()

    self.assertEqual(base.findDistribution('base'), base.Distribution)


class TestDistributionMeta(unittest.TestCase):
  """Test the Distribution metaclass."""
  def test(self):
    class TestDist1(object):
      __metaclass__ = base.DistributionMeta
      _version = 1
    class TestDist2(TestDist1):
      _version = 2
    class TestDist3(TestDist2):
      _version = 3

    self.assertEqual(TestDist3.version, (3, (2, (1,))))


class TestDistributionUpdateDefaults(mox.MoxTestBase):
  class TestDistro(base.Distribution):
    _name = 'testdistro'

    def _initDefaults(self):
      super(TestDistributionUpdateDefaults.TestDistro, self)._initDefaults()

      self.base_defaults.update({'a': '1', 'c': 2})
      self.custom_defaults.update({'b': '3', 'd': 4})

  def setUp(self):
    super(TestDistributionUpdateDefaults, self).setUp()

    self.mock_config = self.mox.CreateMock(ConfigParser.SafeConfigParser)
    self.mox.StubOutWithMock(ConfigParser,
                             'SafeConfigParser',
                             use_mock_anything=True)
    ConfigParser.SafeConfigParser().AndReturn(self.mock_config)

    self.mock_config.read(['/etc/debmarshal/distros.conf'])

  def testBase(self):
    self.mock_config.has_section('testdistro.base').\
        AndReturn(True)
    self.mock_config.items('testdistro.base').\
        AndReturn((('a', '5'), ('b', '6'), ('c', '7')))

    self.mock_config.has_section('testdistro.custom').\
        AndReturn(False)

    self.mox.ReplayAll()

    self.assertEqual(self.TestDistro().base_defaults, {'a': '5', 'c': 2})

  def testCustom(self):
    self.mock_config.has_section('testdistro.base').\
        AndReturn(False)

    self.mock_config.has_section('testdistro.custom').\
        AndReturn(True)
    self.mock_config.items('testdistro.custom').\
        AndReturn((('a', '5'), ('b', '6'), ('c', '7')))

    self.mox.ReplayAll()

    self.assertEqual(self.TestDistro().custom_defaults,
                     {'b': '6', 'd': 4})


class TestDistributionInit(unittest.TestCase):
  """Test base.Distribution.__init__."""
  def testNoArguments(self):
    """Test passing no arguments to Distribution.__init__.

    This should work, but be totally uninteresting.
    """
    distro = NoDefaultsDistribution()

    self.assertEqual(distro.base_config, {})
    self.assertEqual(distro.custom_config, {})

  def testBaseConfig(self):
    """Test missing and extra options to the Distribution base_config."""
    class TestDistro(NoDefaultsDistribution):
      def _initDefaults(self):
        super(TestDistro, self)._initDefaults()

        self.base_defaults.update({'bar': 'baz'})
        self.base_configurable.update(['foo', 'bar'])

    self.assertRaises(errors.InvalidInput, TestDistro,
                      {})
    self.assertRaises(errors.InvalidInput, TestDistro,
                      {'foo': 'spam',
                       'blah': 'eggs'})

  def testCustomConfig(self):
    """Test missing and extra options to the Distribution custom_config."""
    class TestDistro(NoDefaultsDistribution):
      def _initDefaults(self):
        super(TestDistro, self)._initDefaults()

        self.custom_defaults.update({'bar': 'baz'})
        self.custom_configurable.update(['foo', 'bar'])

    self.assertRaises(errors.InvalidInput, TestDistro,
                      None, {})
    self.assertRaises(errors.InvalidInput, TestDistro,
                      None, {'foo': 'spam',
                             'blah': 'eggs'})


class TestDistributionGetItems(unittest.TestCase):
  """Test retrieving image settings from a distribution."""
  def testBaseConfig(self):
    class TestDistro(NoDefaultsDistribution):
      def _initDefaults(self):
        super(TestDistro, self)._initDefaults()

        self.base_configurable.update(['foo'])
        self.base_defaults.update({'bar': 'baz'})

    distro = TestDistro({'foo': 'quux'})

    self.assertEqual(distro.getBaseConfig('foo'), 'quux')
    self.assertEqual(distro.getBaseConfig('bar'), 'baz')
    self.assertRaises(KeyError, distro.getBaseConfig, 'spam')

  def testCustomConfig(self):
    class TestDistro(NoDefaultsDistribution):
      def _initDefaults(self):
        super(TestDistro, self)._initDefaults()

        self.custom_configurable.update(['foo'])
        self.custom_defaults.update({'bar': 'baz'})

    distro = TestDistro(None, {'foo': 'quux'})

    self.assertEqual(distro.getCustomConfig('foo'), 'quux')
    self.assertEqual(distro.getCustomConfig('bar'), 'baz')
    self.assertRaises(KeyError, distro.getCustomConfig, 'spam')

  def testJustDefaults(self):
    class TestDistro(NoDefaultsDistribution):
      def _initDefaults(self):
        super(TestDistro, self)._initDefaults()

        self.base_defaults.update({'bar': 'baz'})
        self.base_configurable.update(['bar'])
        self.custom_defaults.update({'bar': 'baz'})
        self.custom_configurable.update(['bar'])

    self.assertEqual(TestDistro().getBaseConfig('bar'), 'baz')
    self.assertEqual(TestDistro().getCustomConfig('bar'), 'baz')


class TestDistributionHashConfig(unittest.TestCase):
  class TestDistro(NoDefaultsDistribution):
    _name = 'testdistro'

    _version = 2

    def _initDefaults(self):
      super(TestDistributionHashConfig.TestDistro, self)._initDefaults()

      self.base_defaults.update({'a': '1', 'b': '2'})
      self.base_configurable.update('abc')
      self.custom_defaults.update({'d': '1', 'e': '2'})
      self.custom_configurable.update('def')

  def testConsistentHashing(self):
    dist = self.TestDistro({'c': '3'}, {'f': '3'})
    self.assertEqual(dist.hashBaseConfig(), dist.hashBaseConfig())
    self.assertEqual(dist.hashConfig(), dist.hashConfig())

  def testHashSameConfig(self):
    dist1 = self.TestDistro({'c': '3'}, {'f': '3'})
    dist2 = self.TestDistro({'c': '3'}, {'f': '3'})
    self.assertEqual(dist1.hashBaseConfig(), dist2.hashBaseConfig())
    self.assertEqual(dist1.hashConfig(), dist2.hashConfig())

  def testHashSameBaseConfig(self):
    dist1 = self.TestDistro({'c': '3'}, {'f': '3'})
    dist2 = self.TestDistro({'c': '3'}, {'f': '4'})
    self.assertEqual(dist1.hashBaseConfig(), dist2.hashBaseConfig())
    self.assertNotEqual(dist1.hashConfig(), dist2.hashConfig())

  def testHashDifferentConfigs(self):
    dist1 = self.TestDistro({'c': '3'}, {'f': '3'})
    dist2 = self.TestDistro({'c': '4'}, {'f': '4'})
    self.assertNotEqual(dist1.hashBaseConfig(), dist2.hashBaseConfig())
    self.assertNotEqual(dist1.hashConfig(), dist2.hashConfig())


class TestDistributionPaths(unittest.TestCase):
  def test(self):
    class TestDistro(NoDefaultsDistribution):
      def hashBaseConfig(self):
        return 'abcd'

      def hashConfig(self):
        return 'efgh'

    self.assertEqual(TestDistro().basePath(),
                     '/var/cache/debmarshal/images/base/abcd')
    self.assertEqual(TestDistro().customPath(),
                     '/var/cache/debmarshal/images/custom/efgh')


class TestDistributionVerify(mox.MoxTestBase):
  class TestDistro(NoDefaultsDistribution):
    def basePath(self):
      return 'abcd'

    def customPath(self):
      return 'efgh'

  def testBaseExists(self):
    self.mox.StubOutWithMock(os.path, 'exists')

    os.path.exists('abcd').AndReturn(True)
    os.path.exists('efgh').AndReturn(False)

    self.mox.ReplayAll()

    self.assertEqual(self.TestDistro().verifyBase(), True)
    self.assertEqual(self.TestDistro().verifyCustom(), False)

  def testBaseExists(self):
    self.mox.StubOutWithMock(os.path, 'exists')

    os.path.exists('abcd').AndReturn(False)
    os.path.exists('efgh').AndReturn(True)

    self.mox.ReplayAll()

    self.assertEqual(self.TestDistro().verifyBase(), False)
    self.assertEqual(self.TestDistro().verifyCustom(), True)


class TestDistributionCreate(unittest.TestCase):
  def test(self):
    self.assertRaises(errors.NotImplementedError,
                      NoDefaultsDistribution().createBase)
    self.assertRaises(errors.NotImplementedError,
                      NoDefaultsDistribution().createCustom)


if __name__ == '__main__':
  unittest.main()
