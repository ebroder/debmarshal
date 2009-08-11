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
"""tests for debmarshal.distros.ubuntu."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import fcntl
import os
import posix
import re
import shutil
import stat
import string
import struct
import subprocess
import tempfile
import unittest

import mox

from debmarshal.distros import base
from debmarshal.distros import ubuntu
from debmarshal import errors
from debmarshal.tests.distros import test_base
from debmarshal import utils


class TestUbuntu(test_base.NoDefaultsDistribution, ubuntu.Ubuntu):
  """Ubuntu distribution for testing."""


class TestWithoutInitScripts(mox.MoxTestBase):
  def setUp(self):
    super(TestWithoutInitScripts, self).setUp()

    ubuntu.open = self.mox.CreateMockAnything()

  def tearDown(self):
    super(TestWithoutInitScripts, self).tearDown()

    del ubuntu.open

  def test(self):
    f = self.mox.CreateMock(file)
    ubuntu.open('foo/usr/sbin/policy-rc.d', 'w').AndReturn(f)

    f.write("#!/bin/sh\nexit 101\n")
    f.close()

    self.mox.StubOutWithMock(os, 'chmod')
    os.chmod('foo/usr/sbin/policy-rc.d', 0755)

    self.mox.StubOutWithMock(os.path, 'exists')
    os.path.exists('foo/usr/sbin/policy-rc.d').AndReturn(True)

    self.mox.StubOutWithMock(os, 'remove')
    os.remove('foo/usr/sbin/policy-rc.d')

    @ubuntu.withoutInitScripts
    def test(self):
      return True

    self.mox.ReplayAll()

    self.target = 'foo'

    test(self)


class TestUbuntuInit(unittest.TestCase):
  def test(self):
    """Test handling of Dapper-specific kernel config."""
    self.assertEqual(TestUbuntu().getCustomConfig('kernel'),
                     'linux-image-generic')
    self.assertEqual(TestUbuntu({'suite': 'dapper'}).getCustomConfig('kernel'),
                     'linux-image-amd64-generic')
    self.assertEqual(TestUbuntu({'suite': 'dapper',
                                 'arch': 'amd64'}).getCustomConfig('kernel'),
                     'linux-image-amd64-generic')
    self.assertEqual(TestUbuntu({'suite': 'dapper',
                                 'arch': 'i386'}).getCustomConfig('kernel'),
                     'linux-image-686')


class TestUbuntuMountImage(mox.MoxTestBase):
  def setUp(self):
    super(TestUbuntuMountImage, self).setUp()

    self.img = '/home/ebroder/test.img'
    self.root = '/tmp/tmpABCDEF'

    self.mox.StubOutWithMock(tempfile, 'mkdtemp')
    tempfile.mkdtemp().AndReturn(self.root)

    self.mox.StubOutWithMock(base, 'captureCall')
    self.mox.StubOutWithMock(utils, 'diskIsBlockDevice')

  def testBlock(self):
    utils.diskIsBlockDevice(self.img).AndReturn(True)

    base.captureCall(['mount', '-o', 'noatime', self.img, self.root])

    self.mox.ReplayAll()

    deb = TestUbuntu()

    self.assertEqual(deb._mountImage(self.img), self.root)

  def testSuccess(self):
    utils.diskIsBlockDevice(self.img).AndReturn(False)

    base.captureCall(['mount',
                      '-o', 'noatime',
                      '-o', 'loop',
                      self.img, self.root])
    base.captureCall(['umount', '-l', self.root])

    self.mox.StubOutWithMock(os, 'rmdir')
    os.rmdir(self.root)

    self.mox.ReplayAll()

    deb = TestUbuntu()

    self.assertEqual(deb._mountImage(self.img), self.root)
    deb._umountImage(self.root)

  def testFailure(self):
    utils.diskIsBlockDevice(self.img).AndReturn(False)

    base.captureCall(
        ['mount',
         '-o', 'noatime',
         '-o', 'loop',
         self.img, self.root]).AndRaise(
        subprocess.CalledProcessError(
            2,
            ['mount', '-o', 'loop', self.img, self.root]))

    self.mox.StubOutWithMock(os, 'rmdir')
    os.rmdir(self.root)

    self.mox.ReplayAll()

    deb = TestUbuntu()

    self.assertRaises(subprocess.CalledProcessError,
                      deb._mountImage, self.img)


class TestUbuntuVerifyImage(mox.MoxTestBase):
  def setUp(self):
    super(TestUbuntuVerifyImage, self).setUp()

    self.mox.StubOutWithMock(base, 'createCow')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_mountImage')
    self.mox.StubOutWithMock(base, 'captureCall')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_umountImage')
    self.mox.StubOutWithMock(base, 'cleanupCow')

    base.createCow('/home/evan/test.img', 1024 ** 3).AndReturn(
      '/dev/mapper/somethingrandom')
    ubuntu.Ubuntu._mountImage('/dev/mapper/somethingrandom').AndReturn(
      '/tmp/tmp.ABC')

    ubuntu.Ubuntu._umountImage('/tmp/tmp.ABC')
    base.cleanupCow('/dev/mapper/somethingrandom')

  def testUpdateError(self):
    base.captureCall(['chroot', '/tmp/tmp.ABC', 'apt-get', '-qq', 'update']).\
        AndRaise(subprocess.CalledProcessError(1, []))

    self.mox.ReplayAll()

    self.assertEqual(TestUbuntu()._verifyImage('/home/evan/test.img'),
                     False)

  def testGood(self):
    base.captureCall(['chroot', '/tmp/tmp.ABC', 'apt-get', '-qq', 'update']).\
        AndReturn('')

    base.captureCall(['chroot', '/tmp/tmp.ABC', 'apt-get',
                      '-o', 'Debug::NoLocking=true',
                      '-sqq',
                      'dist-upgrade']).AndReturn('\n')

    self.mox.ReplayAll()

    self.assertEqual(TestUbuntu()._verifyImage('/home/evan/test.img'),
                     True)

  def testBad(self):
    base.captureCall(['chroot', '/tmp/tmp.ABC', 'apt-get', '-qq', 'update']).\
        AndReturn('')

    base.captureCall(['chroot', '/tmp/tmp.ABC', 'apt-get',
                      '-o', 'Debug::NoLocking=true',
                      '-sqq',
                      'dist-upgrade']).AndReturn("""
Inst libruby1.8 [1.8.6.111-2ubuntu1.2] (1.8.6.111-2ubuntu1.3 Ubuntu:8.04/hardy-security)
Conf libruby1.8 (1.8.6.111-2ubuntu1.3 Ubuntu:8.04/hardy-security
""")

    self.mox.ReplayAll()

    self.assertEqual(TestUbuntu()._verifyImage('/home/evan/test.img'),
                     False)


class TestUbuntuVerifyBase(mox.MoxTestBase):
  def setUp(self):
    super(TestUbuntuVerifyBase, self).setUp()

    self.mox.StubOutWithMock(utils, 'acquireLock')
    utils.acquireLock(
        'debmarshal-base-dist-%s' % TestUbuntu().hashBaseConfig(),
        fcntl.LOCK_EX)

    self.mox.StubOutWithMock(base.Distribution, 'verifyBase')
    self.mox.StubOutWithMock(base, 'setupLoop')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_verifyImage')
    self.mox.StubOutWithMock(base, 'cleanupLoop')

  def testNoExists(self):
    base.Distribution.verifyBase().AndReturn(False)

    self.mox.ReplayAll()

    self.assertEqual(TestUbuntu().verifyBase(), False)

  def testExists(self):
    base.Distribution.verifyBase().AndReturn(True)

    base.setupLoop(mox.IgnoreArg()).AndReturn('/dev/loop0')
    ubuntu.Ubuntu._verifyImage('/dev/loop0').AndReturn(False)
    base.cleanupLoop('/dev/loop0')

    self.mox.ReplayAll()

    self.assertEqual(TestUbuntu().verifyBase(), False)

  def testAllGood(self):
    base.Distribution.verifyBase().AndReturn(True)

    base.setupLoop(mox.IgnoreArg()).AndReturn('/dev/loop0')
    ubuntu.Ubuntu._verifyImage('/dev/loop0').AndReturn(True)
    base.cleanupLoop('/dev/loop0')

    self.mox.ReplayAll()

    self.assertEqual(TestUbuntu().verifyBase(), True)


class TestUbuntuVerifyCustom(mox.MoxTestBase):
  def test(self):
    self.mox.StubOutWithMock(utils, 'acquireLock')
    utils.acquireLock(
        'debmarshal-custom-dist-%s' % TestUbuntu(
            None, {'hostname': 'www', 'domain': 'example.com'}).hashConfig(),
        fcntl.LOCK_EX)

    self.mox.StubOutWithMock(base.Distribution, 'verifyCustom')

    base.Distribution.verifyCustom().AndReturn(False)

    self.mox.ReplayAll()

    self.assertEqual(
        TestUbuntu(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        False)

class TestUbuntuVerifyCustomExists(mox.MoxTestBase):
  def setUp(self):
    super(TestUbuntuVerifyCustomExists, self).setUp()

    self.mox.StubOutWithMock(utils, 'acquireLock')
    utils.acquireLock(
        'debmarshal-custom-dist-%s' % TestUbuntu(
            None, {'hostname': 'www', 'domain': 'example.com'}).hashConfig(),
        fcntl.LOCK_EX)

    self.mox.StubOutWithMock(base.Distribution, 'verifyCustom')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_verifyImage')
    base.Distribution.verifyCustom().AndReturn(True)

    self.mox.StubOutWithMock(base, 'setupLoop')
    base.setupLoop(mox.IgnoreArg()).AndReturn('/dev/loop0')

    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_cleanupDevices')
    self.mox.StubOutWithMock(base, 'cleanupLoop')

    ubuntu.Ubuntu._cleanupDevices('/dev/loop0')
    base.cleanupLoop('/dev/loop0')

    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_setupDevices')

  def testExists(self):
    ubuntu.Ubuntu._setupDevices('/dev/loop0').AndReturn('/dev/mapper/loop0')
    ubuntu.Ubuntu._verifyImage('/dev/mapper/loop01').AndReturn(False)

    self.mox.ReplayAll()

    self.assertEqual(
        TestUbuntu(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        False)

  def testAllGood(self):
    ubuntu.Ubuntu._setupDevices('/dev/loop0').AndReturn('/dev/mapper/loop0')

    ubuntu.Ubuntu._verifyImage('/dev/mapper/loop01').AndReturn(True)

    self.mox.ReplayAll()

    self.assertEqual(
        TestUbuntu(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        True)

  def testError(self):
    ubuntu.Ubuntu._setupDevices('/dev/loop0').AndRaise(
        Exception("Test exception"))

    self.mox.ReplayAll()

    self.assertEqual(
        TestUbuntu(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        False)


class TestUbuntuRunInTarget(mox.MoxTestBase):
  def test(self):
    self.mox.StubOutWithMock(base, 'captureCall')

    base.captureCall(['chroot', 'foo', 'some', 'command'])

    self.mox.ReplayAll()

    deb = TestUbuntu()
    deb.target = 'foo'
    deb._runInTarget(['some', 'command'])


class TestUbuntuInstallFilesystem(unittest.TestCase):
  def test(self):
    fd, name = tempfile.mkstemp()
    os.close(fd)

    try:
      deb = TestUbuntu()
      base.createSparseFile(name, 1024**3)
      deb._installFilesystem(name)

      # Let's simulate libmagic to test if name contains an ext3
      # filesystem (really, just any version of ext >=2, but that's
      # good enough)
      fd = open(name)
      fd.seek(0x438)
      leshort = 'H'
      size = struct.calcsize(leshort)
      self.assertEqual(struct.unpack(leshort, fd.read(size))[0],
                       0xEF53)
    finally:
      os.remove(name)
  test.slow = 1


class TestUbuntuInstallSwap(unittest.TestCase):
  def test(self):
    fd, name = tempfile.mkstemp()
    os.close(fd)

    try:
      deb = TestUbuntu()
      base.createSparseFile(name, 1024**3)
      deb._installSwap(name)

      # Test that what we ended up with is actually swapspace.
      fd = open(name)
      fd.seek(4086)
      self.assertEqual(fd.read(10), 'SWAPSPACE2')
    finally:
      os.remove(name)
  test.slow = 1


class TestMethodsWithoutInitScripts(mox.MoxTestBase):
  """Superclass for testing methods wrapped in withoutInitScripts."""
  def setUp(self):
    super(TestMethodsWithoutInitScripts, self).setUp()

    self.mox.StubOutWithMock(ubuntu, '_stopInitScripts')
    self.mox.StubOutWithMock(ubuntu, '_startInitScripts')

    ubuntu._stopInitScripts(mox.IgnoreArg())
    ubuntu._startInitScripts(mox.IgnoreArg())


class TestUbuntuInstallPackage(TestMethodsWithoutInitScripts):
  def test(self):
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_runInTarget')

    env = dict(os.environ)
    env['DEBIAN_FRONTEND'] = 'noninteractive'
    ubuntu.Ubuntu._runInTarget(['apt-get', '-y', 'install', 'foo', 'bar'],
                               env=env)

    self.mox.ReplayAll()

    deb = TestUbuntu()
    deb.target = 'blah'
    deb._installPackages('foo', 'bar')


class TestUbuntuInstallReconfigure(TestMethodsWithoutInitScripts):
  def test(self):
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_runInTarget')

    ubuntu.Ubuntu._runInTarget(['dpkg-reconfigure',
                                '-fnoninteractive',
                                '-pcritical',
                                'foo'])

    self.mox.ReplayAll()

    deb = TestUbuntu()
    deb.target = 'blah'
    deb._installReconfigure('foo')


class TestUbuntuInstallDebootstrap(mox.MoxTestBase):
  def test(self):
    self.mox.StubOutWithMock(base, 'captureCall')

    deb = TestUbuntu()
    deb.target = 'blah'

    base.captureCall([
        'debootstrap',
        '--keyring=/usr/share/keyrings/ubuntu-archive-keyring.gpg',
        '--arch=amd64',
        '--components=main,restricted,universe,multiverse',
        'jaunty',
        'blah',
        'http://us.archive.ubuntu.com/ubuntu/'])

    self.mox.ReplayAll()

    deb._installDebootstrap()


class TestUbuntuInstallHosts(unittest.TestCase):
  def test(self):
    target = tempfile.mkdtemp()
    hosts_dir = os.path.join(target, 'etc')
    os.mkdir(hosts_dir)

    try:
      deb = TestUbuntu()
      deb.target = target

      deb._installHosts()

      hosts = os.path.join(hosts_dir, 'hosts')
      self.assert_(os.path.exists(hosts))
      self.assert_(re.search('^127\.0\.0\.1\s+localhost',
                             open(hosts).read(),
                             re.M))
    finally:
      shutil.rmtree(target)


class TestUbuntuInstallSources(unittest.TestCase):
  def testNoComponents(self):
    target = tempfile.mkdtemp()
    sources_dir = os.path.join(target, 'etc/apt')
    os.makedirs(sources_dir)

    try:
      deb = TestUbuntu({'enable_security': False,
                        'enable_updates': False,
                        'enable_backports': False,
                        'enable_proposed': False})
      deb.target = target

      deb._installSources()

      sources_path = os.path.join(sources_dir, 'sources.list')
      sources = open(sources_path).read()

      self.assert_(re.search(
          '^deb http://us\.archive\.ubuntu\.com/ubuntu/',
          sources,
          re.M))
      self.assert_(not re.search(
          '^deb http://security\.ubuntu\.com/ubuntu/ jaunty-security',
          sources,
          re.M))
      self.assert_(not re.search(
          '^deb http://us\.archive\.ubuntu\.com/ubuntu/ jaunty-updates',
          sources,
          re.M))
      self.assert_(not re.search(
          '^deb http://us\.archive\.ubuntu\.com/ubuntu/ jaunty-backports',
          sources,
          re.M))
      self.assert_(not re.search(
          '^deb http://us\.archive\.ubuntu\.com/ubuntu/ jaunty-proposed',
          sources,
          re.M))
    finally:
      shutil.rmtree(target)

  def testAllComponents(self):
    target = tempfile.mkdtemp()
    sources_dir = os.path.join(target, 'etc/apt')
    os.makedirs(sources_dir)

    try:
      deb = TestUbuntu({'enable_security': True,
                        'enable_updates': True,
                        'enable_backports': True,
                        'enable_proposed': True})
      deb.target = target

      deb._installSources()

      sources_path = os.path.join(sources_dir, 'sources.list')
      sources = open(sources_path).read()

      self.assert_(re.search(
          '^deb http://us\.archive\.ubuntu\.com/ubuntu/ jaunty',
          sources,
          re.M))
      self.assert_(re.search(
          '^deb http://security\.ubuntu\.com/ubuntu/ jaunty-security',
          sources,
          re.M))
      self.assert_(re.search(
          '^deb http://us\.archive\.ubuntu\.com/ubuntu/ jaunty-updates',
          sources,
          re.M))
      self.assert_(re.search(
          '^deb http://us\.archive\.ubuntu\.com/ubuntu/ jaunty-backports',
          sources,
          re.M))
      self.assert_(re.search(
          '^deb http://us\.archive\.ubuntu\.com/ubuntu/ jaunty-proposed',
          sources,
          re.M))
    finally:
      shutil.rmtree(target)


class TestUbuntuInstallUpdates(TestMethodsWithoutInitScripts):
  def test(self):
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_runInTarget')

    env = dict(os.environ)
    env['DEBIAN_FRONTEND'] = 'noninteractive'

    ubuntu.Ubuntu._runInTarget(['apt-get', 'update'], env=env)
    ubuntu.Ubuntu._runInTarget(['apt-get', '-y', 'dist-upgrade'], env=env)

    self.mox.ReplayAll()

    deb = TestUbuntu()
    deb.target = 'foo'
    deb._installUpdates()


class TestUbuntuInstallLocale(TestMethodsWithoutInitScripts):
  def test(self):
    target = tempfile.mkdtemp()
    etc_dir = os.path.join(target, 'etc')
    os.makedirs(etc_dir)

    defaults_dir = os.path.join(target, 'etc/default')
    os.makedirs(defaults_dir)

    try:
      self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installPackages')
      self.mox.StubOutWithMock(ubuntu.Ubuntu, '_runInTarget')
      self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installReconfigure')

      ubuntu.Ubuntu._installPackages('locales')
      ubuntu.Ubuntu._runInTarget(['locale-gen'])
      ubuntu.Ubuntu._installReconfigure('locales')

      self.mox.ReplayAll()

      deb = TestUbuntu()
      deb.target = target
      deb._installLocale()

      self.assertEqual(open(os.path.join(etc_dir, 'locale.gen')).read(),
                       'en_US.UTF-8 UTF-8\n')
      self.assertEqual(open(os.path.join(defaults_dir, 'locale')).read(),
                       'LANG="en_US.UTF-8"\n')
    finally:
      shutil.rmtree(target)


class TestUbuntuInstallTimezone(TestMethodsWithoutInitScripts):
  def setUp(self):
    super(TestUbuntuInstallTimezone, self).setUp()

    self.target = tempfile.mkdtemp()
    self.etc_dir = os.path.join(self.target, 'etc')
    os.makedirs(self.etc_dir)

    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installReconfigure')

  def tearDown(self):
    shutil.rmtree(self.target)

    super(TestUbuntuInstallTimezone, self).tearDown()

  def testRecent(self):
    ubuntu.Ubuntu._installReconfigure('tzdata')

    self.mox.ReplayAll()

    deb = TestUbuntu()
    deb.target = self.target
    deb._installTimezone()

    self.assertEqual(
        open(os.path.join(self.etc_dir, 'timezone')).read().strip(),
        'America/Los_Angeles')

  def testDapper(self):
    ubuntu.Ubuntu._installReconfigure('locales')

    self.mox.ReplayAll()

    deb = TestUbuntu({'suite': 'dapper'})
    deb.target = self.target
    deb._installTimezone()


class TestUbuntuInstallPartitions(unittest.TestCase):
  def test(self):
    fd, name = tempfile.mkstemp()
    os.close(fd)
    size = 10 * (1024 ** 3)
    base.createSparseFile(name, size)

    try:
      TestUbuntu()._installPartitions(name)

      fd = open(name)
      fd.seek(0x01BE)
      self.assertEqual(fd.read(1), '\x80',
                       'First partition is not bootable.')
      fd.seek(0x01BE + 0x4)
      self.assertEqual(fd.read(1), '\x83',
                       'First partition is not of type Linux.')

      fd.seek(0x01BE + 0x10 + 0x4)
      self.assertEqual(fd.read(1), '\x82',
                       'Second partition is not of type swap.')
      fd.seek(0x01BE + 0x10 + 0xC)
      swap_bytes = struct.unpack('<L', fd.read(4))[0] * 512
      desired_swap = 1024 ** 3
      variance = 128 * (1024 ** 2)
      self.assert_(abs(swap_bytes - desired_swap) < variance,
                   'Swap partition is too far off from 1G.')

      fd.seek(0x01BE + 0x20 + 0x4)
      self.assertEqual(fd.read(1), '\x00',
                       'Third partition exists.')

      fd.seek(0x01BE + 0x30 + 0x4)
      self.assertEqual(fd.read(1), '\x00',
                       'Fourth partition exists.')
    finally:
      os.remove(name)
  test.slow = 1


class TestUbuntuDevices(mox.MoxTestBase):
  def testSetup(self):
    self.mox.StubOutWithMock(base, 'captureCall')

    base.captureCall(['kpartx', '-p', '', '-a', '/dev/loop0'])

    self.mox.ReplayAll()

    self.assertEqual(TestUbuntu()._setupDevices('/dev/loop0'),
                     '/dev/mapper/loop0')

  def testCleanup(self):
    self.mox.StubOutWithMock(base, 'captureCall')

    base.captureCall(['kpartx', '-p', '', '-d', '/dev/loop0'])

    self.mox.ReplayAll()

    TestUbuntu()._cleanupDevices('/dev/loop0')


class TestUbuntuMapper(mox.MoxTestBase):
  def testSetupSuccess(self):
    self.mox.StubOutWithMock(os, 'stat')
    self.mox.StubOutWithMock(base, 'captureCall')

    base.captureCall(['blockdev', '--getsz', '/dev/loop1']).AndReturn(
        '1024\n')
    os.stat('/dev/loop1').AndReturn(posix.stat_result([
          # st_rdev is the 16th argument
          0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
          0, 0, 0, 0, 0, os.makedev(7, 1)]))

    for disk_id in 'abcdefg':
      base.captureCall(['dmsetup', 'create', 'sd%s' % disk_id],
                       stdin_str=mox.IgnoreArg()).AndRaise(
          subprocess.CalledProcessError(1, 'Some error'))

    base.captureCall(['dmsetup', 'create', 'sdh'],
                     stdin_str='0 1024 linear 7:1 0')

    self.mox.ReplayAll()

    TestUbuntu()._setupMapper('/dev/loop1')

  def testSetupFailure(self):
    self.mox.StubOutWithMock(os, 'stat')
    self.mox.StubOutWithMock(base, 'captureCall')

    base.captureCall(['blockdev', '--getsz', '/dev/loop1']).AndReturn(
        '1024\n')
    os.stat('/dev/loop1').AndReturn(posix.stat_result([
          # st_rdev is the 16th argument
          0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
          0, 0, 0, 0, 0, os.makedev(7, 1)]))

    for disk_type in ('sd', 'hd', 'vd'):
      for disk_id in string.ascii_lowercase:
        base.captureCall(['dmsetup', 'create', disk_type + disk_id],
                         stdin_str=mox.IgnoreArg()).AndRaise(
            subprocess.CalledProcessError(1, 'Some error'))

    self.mox.ReplayAll()

    self.assertRaises(errors.NoAvailableDevs, TestUbuntu()._setupMapper,
                      '/dev/loop1')

  def testCleanup(self):
    self.mox.StubOutWithMock(base, 'captureCall')

    base.captureCall(['dmsetup', 'remove', 'sdc'])

    self.mox.ReplayAll()

    TestUbuntu()._cleanupMapper('/dev/mapper/sdc')


class TestUbuntuCopyFilesystem(unittest.TestCase):
  def test(self):
    src = tempfile.mkdtemp()
    dst = tempfile.mkdtemp()

    try:
      if src.endswith('/'):
        src = src[:-1]
      if dst.endswith('/'):
        dst = src[:-1]

      open(os.path.join(src, 'test_file'), 'w').write('Hello world\n')
      open(os.path.join(src, 'test_executable'), 'w').write(
          "#!/bin/sh\necho Hello world\n")
      os.chmod(os.path.join(src, 'test_executable'), 0755)
      os.symlink('blah', os.path.join(src, 'test_symlink'))

      TestUbuntu()._copyFilesystem(src, dst)

      self.assertEqual(open(os.path.join(dst, 'test_file')).read(),
                       'Hello world\n')
      self.assertEqual(
          stat.S_IMODE(
              os.stat(os.path.join(dst, 'test_executable')).st_mode),
          0755)
      self.assert_(
          stat.S_ISLNK(os.lstat(os.path.join(dst, 'test_symlink')).st_mode))
      self.assertEqual(os.readlink(os.path.join(dst, 'test_symlink')),
                       'blah')
    finally:
      shutil.rmtree(src)
      shutil.rmtree(dst)


class TestUbuntuInstallFstab(mox.MoxTestBase):
  def testSuccess(self):
    target = tempfile.mkdtemp()

    try:
      os.makedirs(os.path.join(target, 'etc'))

      self.mox.StubOutWithMock(os.path, 'exists')
      os.path.exists('/dev/vg/root').InAnyOrder().AndReturn(True)
      os.path.exists('/dev/vg/var').InAnyOrder().AndReturn(True)
      os.path.exists('/dev/vg/swap').InAnyOrder().AndReturn(True)

      self.mox.StubOutWithMock(base, 'captureCall')
      base.captureCall(['blkid', '-o', 'value', '-s', 'UUID', '/dev/vg/root']).\
          InAnyOrder().\
          AndReturn('00000000-0000-0000-0000-000000000000\n')
      base.captureCall(['blkid', '-o', 'value', '-s', 'UUID', '/dev/vg/var']).\
          InAnyOrder().\
          AndReturn('11111111-1111-1111-1111-111111111111\n')
      base.captureCall(['blkid', '-o', 'value', '-s', 'UUID', '/dev/vg/swap']).\
          InAnyOrder().\
          AndReturn('22222222-2222-2222-2222-222222222222\n')

      self.mox.ReplayAll()

      deb = TestUbuntu()
      deb.target = target

      deb._installFstab({'/': '/dev/vg/root',
                         '/var': '/dev/vg/var',
                         'swap': '/dev/vg/swap'})

      fstab = open(os.path.join(target, 'etc/fstab')).read()

      self.assert_(re.search(
          '^/dev/disk/by-uuid/[-0]{36}\s+/\s+ext3\s+defaults\s+0\s+1',
          fstab,
          re.M))
      self.assert_(re.search(
          '^/dev/disk/by-uuid/[-1]{36}\s+/var\s+ext3\s+defaults\s+0\s+2',
          fstab,
          re.M))
      self.assert_(re.search(
          '^/dev/disk/by-uuid/[-2]{36}\s+none\s+swap\s+defaults\s+0\s+0',
          fstab,
          re.M))
    finally:
      shutil.rmtree(target)

  def testValidationError(self):
    target = tempfile.mkdtemp()

    try:
      os.makedirs(os.path.join(target, 'etc'))

      self.mox.StubOutWithMock(os.path, 'exists')
      os.path.exists('/dev/vg/root').AndReturn(False)

      self.mox.ReplayAll()

      deb = TestUbuntu()
      deb.target = target

      self.assertRaises(errors.NotFound, deb._installFstab,
                        {'/': '/dev/vg/root'})
    finally:
      shutil.rmtree(target)


class TestUbuntuInstallNetwork(unittest.TestCase):
  def testDhcp(self):
    target = tempfile.mkdtemp()

    try:
      os.makedirs(os.path.join(target, 'etc/network'))

      deb = TestUbuntu(None, {'hostname': 'web',
                              'domain': 'example.com',
                              'dhcp': True})
      deb.target = target

      deb._installNetwork()

      hosts = open(os.path.join(target, 'etc/hosts')).read()
      self.assert_(re.search(
          '^127\.0\.1\.1\s+web\.example\.com\s+web',
          hosts,
          re.M))

      hostname = open(os.path.join(target, 'etc/hostname')).read()
      self.assertEqual(hostname.strip(), 'web')

      interfaces = open(os.path.join(target, 'etc/network/interfaces')).read()
      self.assert_(re.search(
          'auto\s+lo\niface\s+lo\s+inet\s+loopback',
          interfaces))
      self.assert_(re.search(
          'auto\s+eth0\niface\s+eth0\s+inet\s+dhcp',
          interfaces))
    finally:
      shutil.rmtree(target)

  def testStatic(self):
    target = tempfile.mkdtemp()

    try:
      os.makedirs(os.path.join(target, 'etc/network'))

      deb = TestUbuntu(None, {'hostname': 'web',
                              'domain': 'example.com',
                              'dhcp': False,
                              'ip': '192.168.1.2',
                              'netmask': '255.255.255.0',
                              'gateway': '192.168.1.1',
                              'dns': ['192.168.1.1', '4.2.2.2']})
      deb.target = target

      deb._installNetwork()

      interfaces = open(os.path.join(target, 'etc/network/interfaces')).read()
      for r in ['^\s+address 192\.168\.1\.2$',
                '^\s+netmask 255\.255\.255\.0$',
                '^\s+gateway 192\.168\.1\.1$',
                '^\s+dns-nameservers 192\.168\.1\.1 4\.2\.2\.2$',
                '^\s+dns-search example\.com$']:
        self.assert_(re.search(r, interfaces, re.M))
    finally:
      shutil.rmtree(target)


class TestUbuntuInstallKernelConfig(unittest.TestCase):
  def test(self):
    target = tempfile.mkdtemp()

    try:
      os.makedirs(os.path.join(target, 'etc'))

      deb = TestUbuntu()
      deb.target = target

      deb._installKernelConfig()

      kernel_img = open(os.path.join(target, 'etc/kernel-img.conf')).read()
      self.assert_(re.search(
          '^do_initrd\s*=\s*yes$',
          kernel_img,
          re.M))
    finally:
      shutil.rmtree(target)


class TestUbuntuInstallBootloader(mox.MoxTestBase):
  def test(self):
    target = tempfile.mkdtemp()

    try:
      self.mox.StubOutWithMock(base, 'captureCall')
      base.captureCall(['grub-install',
                        '--root-directory=%s' % target,
                        '/dev/mapper/sdc'])

      self.mox.StubOutWithMock(ubuntu.Ubuntu, '_runInTarget')
      ubuntu.Ubuntu._runInTarget(['bash', 'update-grub', '-y'])

      base.captureCall(['blkid',
                        '-o', 'value',
                        '-s', 'UUID',
                        '/dev/mapper/sdc1']).AndReturn(
          "00000000-0000-0000-0000-000000000000")

      def _validateSed(arg):
        return (arg[0] == 'sed' and
                arg[-1] == '/boot/grub/menu.lst')

      ubuntu.Ubuntu._runInTarget(mox.Func(_validateSed))
      ubuntu.Ubuntu._runInTarget(['bash', 'update-grub', '-y'])

      self.mox.ReplayAll()

      deb = TestUbuntu()
      deb.target = target

      deb._installBootloader('/dev/mapper/sdc', '/dev/mapper/sdc1')

      device_map = open(os.path.join(target, 'boot/grub/device.map')).read()
      self.assert_(re.search(
          '^\(hd0\)\s+/dev/mapper/sdc$',
          device_map,
          re.M))
    finally:
      shutil.rmtree(target)


class TestUbuntuInstallExtraPackages(mox.MoxTestBase):
  def test(self):
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installPackages')

    ubuntu.Ubuntu._installPackages('barnowl', 'config-package-dev')
    ubuntu.Ubuntu._installPackages('ubufox-', 'branding-ubuntu-')

    self.mox.ReplayAll()

    deb = TestUbuntu(None, {'add_pkg': ['barnowl', 'config-package-dev'],
                            'rm_pkg': ['ubufox', 'branding-ubuntu'],
                            'hostname': 'www',
                            'domain': 'example.com'})
    deb._installExtraPackages()


class TestUbuntuInstallSSHKey(unittest.TestCase):
  def test(self):
    target = tempfile.mkdtemp()

    try:
      deb = TestUbuntu(None, {'hostname': 'www',
                              'domain': 'example.com',
                              'ssh_key': 'some_ssh_key'})
      deb.target = target
      deb._installSSHKey()

      authorized_keys = open(
          os.path.join(target, 'root/.ssh/authorized_keys')).read()
      self.assert_(re.search(
          '^some_ssh_key$',
          authorized_keys,
          re.M))
    finally:
      shutil.rmtree(target)


class TestUbuntuCreateBase(mox.MoxTestBase):
  def setUp(self):
    super(TestUbuntuCreateBase, self).setUp()

    self.mox.StubOutWithMock(utils, 'acquireLock')
    utils.acquireLock(
        'debmarshal-base-dist-%s' % TestUbuntu().hashBaseConfig(),
        fcntl.LOCK_EX)

    self.mox.StubOutWithMock(ubuntu.Ubuntu, 'verifyBase')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, 'basePath')
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(os, 'remove')
    self.mox.StubOutWithMock(base, 'createSparseFile')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installFilesystem')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_mountImage')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installDebootstrap')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installHosts')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installSources')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installUpdates')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installLocale')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installTimezone')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_umountImage')

    ubuntu.Ubuntu.verifyBase().AndReturn(False)

    ubuntu.Ubuntu.basePath().MultipleTimes().AndReturn('abcd')
    os.path.exists('abcd').AndReturn(True)
    os.remove('abcd')

    base.createSparseFile('abcd', 1024 ** 3)
    ubuntu.Ubuntu._installFilesystem('abcd')
    ubuntu.Ubuntu._mountImage('abcd').AndReturn('dcba')

    # The order these get called in does actually
    # matter. Unfortunately, we can't test that across multiple
    # MockMethods.
    ubuntu.Ubuntu._installDebootstrap()
    ubuntu.Ubuntu._installHosts()
    ubuntu.Ubuntu._installSources()
    ubuntu.Ubuntu._installUpdates()
    ubuntu.Ubuntu._installLocale()
    ubuntu.Ubuntu._umountImage('dcba')

  def testSuccess(self):
    ubuntu.Ubuntu._installTimezone()

    ubuntu.Ubuntu.verifyBase().AndReturn(True)

    self.mox.ReplayAll()

    # The first time we try, verifyBase returns False. Since the rest
    # of the method has only been stubbed out once, if returning True
    # doesn't cause us to return, then we'll throw errors about
    # methods being called too many times.
    TestUbuntu().createBase()
    TestUbuntu().createBase()

  def testFailure(self):
    # We want to be sure that /all/ of the cleanup still runs, even if
    # there's an exception
    ubuntu.Ubuntu._installTimezone().AndRaise(
        subprocess.CalledProcessError(1, []))

    os.remove('abcd')

    self.mox.ReplayAll()

    self.assertRaises(Exception, TestUbuntu().createBase)


class TestUbuntuInstallCustom(mox.MoxTestBase):
  def setUp(self):
    super(TestUbuntuInstallCustom, self).setUp()

    self.mox.StubOutWithMock(utils, 'acquireLock')
    utils.acquireLock(
        'debmarshal-custom-dist-%s' % TestUbuntu(None,
                                                 {'hostname': 'www',
                                                  'domain': 'example.com'}
                                                 ).hashConfig(),
        fcntl.LOCK_EX)

    self.mox.StubOutWithMock(ubuntu.Ubuntu, 'verifyCustom')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, 'createBase')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, 'basePath')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, 'customPath')
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(os, 'remove')
    self.mox.StubOutWithMock(base, 'createSparseFile')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installPartitions')
    self.mox.StubOutWithMock(base, 'setupLoop')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_setupMapper')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_setupDevices')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installFilesystem')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installSwap')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_mountImage')
    self.mox.StubOutWithMock(base, 'createCow')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_copyFilesystem')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_umountImage')
    self.mox.StubOutWithMock(base, 'cleanupCow')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installUpdates')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installFstab')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installNetwork')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installKernelConfig')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installPackages')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installBootloader')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installExtraPackages')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installSSHKey')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_cleanupDevices')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_cleanupMapper')
    self.mox.StubOutWithMock(base, 'cleanupLoop')

    ubuntu.Ubuntu.verifyCustom().AndReturn(False)

    ubuntu.Ubuntu.createBase()

    ubuntu.Ubuntu.basePath().MultipleTimes().AndReturn('/base')
    ubuntu.Ubuntu.customPath().MultipleTimes().AndReturn('/custom')

    os.path.exists('/custom').AndReturn(True)
    os.remove('/custom')

    base.createSparseFile('/custom', 10 * (1024 ** 3))
    ubuntu.Ubuntu._installPartitions('/custom')
    base.setupLoop('/custom').AndReturn('/dev/loop0')
    ubuntu.Ubuntu._setupMapper('/dev/loop0').AndReturn('/dev/mapper/sda')
    ubuntu.Ubuntu._setupDevices('/dev/mapper/sda').AndReturn('/dev/mapper/sda')
    ubuntu.Ubuntu._installFilesystem('/dev/mapper/sda1')
    ubuntu.Ubuntu._installSwap('/dev/mapper/sda2')

    ubuntu.Ubuntu._mountImage('/dev/mapper/sda1').AndReturn('/tmp/tmpnew')
    utils.acquireLock(
        'debmarshal-base-dist-%s' % TestUbuntu(None,
                                                 {'hostname': 'www',
                                                  'domain': 'example.com'}
                                                 ).hashBaseConfig(),
        fcntl.LOCK_SH)
    base.setupLoop('/base').AndReturn('/dev/loop1')
    base.createCow('/dev/loop1', mox.IgnoreArg()).AndReturn(
      '/dev/mapper/cow')
    ubuntu.Ubuntu._mountImage('/dev/mapper/cow').AndReturn('/tmp/tmpold')

    ubuntu.Ubuntu._copyFilesystem('/tmp/tmpold', '/tmp/tmpnew')
    ubuntu.Ubuntu._umountImage('/tmp/tmpold')
    base.cleanupCow('/dev/mapper/cow')
    base.cleanupLoop('/dev/loop1')

    ubuntu.Ubuntu._installUpdates()
    ubuntu.Ubuntu._installFstab({'/': '/dev/mapper/sda1',
                                 'swap': '/dev/mapper/sda2'})
    ubuntu.Ubuntu._installNetwork()
    ubuntu.Ubuntu._installKernelConfig()
    ubuntu.Ubuntu._installPackages('grub')
    ubuntu.Ubuntu._installPackages('linux-image-generic')
    ubuntu.Ubuntu._installBootloader('/dev/mapper/sda', '/dev/mapper/sda1')
    ubuntu.Ubuntu._installExtraPackages()

    # And finally the cleanup that will happen
    ubuntu.Ubuntu._umountImage('/tmp/tmpnew')
    ubuntu.Ubuntu._cleanupDevices('/dev/mapper/sda')
    ubuntu.Ubuntu._cleanupMapper('/dev/mapper/sda')
    base.cleanupLoop('/dev/loop0')

  def testSuccess(self):
    ubuntu.Ubuntu._installSSHKey()

    ubuntu.Ubuntu.verifyCustom().AndReturn(True)
    self.mox.ReplayAll()

    # The first time we try, verifyBase returns False. Since the rest
    # of the method has only been stubbed out once, if returning True
    # doesn't cause us to return, then we'll throw errors about
    # methods being called too many times.
    TestUbuntu(None,
               {'hostname': 'www', 'domain': 'example.com'}).createCustom()
    TestUbuntu(None,
               {'hostname': 'www', 'domain': 'example.com'}).createCustom()

  def testFailure(self):
    ubuntu.Ubuntu._installSSHKey().AndRaise(Exception('An error!'))

    os.remove('/custom')

    self.mox.ReplayAll()

    self.assertRaises(
        Exception,
        TestUbuntu(None,
                   {'hostname': 'www', 'domain': 'example.com'}).createCustom)


if __name__ == '__main__':
  unittest.main()
