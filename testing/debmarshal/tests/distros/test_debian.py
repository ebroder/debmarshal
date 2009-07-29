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
"""tests for debmarshal.distros.debian."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import os
import re
import shutil
import stat
import struct
import subprocess
import tempfile
import unittest

import mox

from debmarshal.distros import base
from debmarshal.distros import debian
from debmarshal.tests.distros import test_base
from debmarshal import utils


class TestDebian(test_base.NoDefaultsDistribution, debian.Debian):
  """Debian distribution for testing."""


class TestWithoutInitScripts(mox.MoxTestBase):
  def setUp(self):
    super(TestWithoutInitScripts, self).setUp()

    debian.open = self.mox.CreateMockAnything()

  def tearDown(self):
    super(TestWithoutInitScripts, self).tearDown()

    del debian.open

  def test(self):
    f = self.mox.CreateMock(file)
    debian.open('foo/usr/sbin/policy-rc.d', 'w').AndReturn(f)

    f.write("#!/bin/sh\nexit 101\n")
    f.close()

    self.mox.StubOutWithMock(os, 'chmod')
    os.chmod('foo/usr/sbin/policy-rc.d', 0755)

    self.mox.StubOutWithMock(os.path, 'exists')
    os.path.exists('foo/usr/sbin/policy-rc.d').AndReturn(True)

    self.mox.StubOutWithMock(os, 'remove')
    os.remove('foo/usr/sbin/policy-rc.d')

    @debian.withoutInitScripts
    def test(self):
      return True

    self.mox.ReplayAll()

    self.target = 'foo'

    test(self)


class TestDebianInit(unittest.TestCase):
  def test(self):
    self.assertEqual(TestDebian().custom_defaults['kernel'],
                     'linux-image-amd64')
    self.assertEqual(TestDebian({'arch': 'arm'}).custom_defaults['kernel'],
                     'linux-image-versatile')


class TestDebianMountImage(mox.MoxTestBase):
  def setUp(self):
    super(TestDebianMountImage, self).setUp()

    self.img = '/home/ebroder/test.img'
    self.root = '/tmp/tmpABCDEF'

    self.mox.StubOutWithMock(tempfile, 'mkdtemp')
    tempfile.mkdtemp().AndReturn(self.root)

    self.mox.StubOutWithMock(base, 'captureCall')
    self.mox.StubOutWithMock(utils, 'diskIsBlockDevice')

  def testBlock(self):
    utils.diskIsBlockDevice(self.img).AndReturn(True)

    base.captureCall(['mount', self.img, self.root])

    self.mox.ReplayAll()

    deb = TestDebian()

    self.assertEqual(deb._mountImage(self.img), self.root)

  def testSuccess(self):
    utils.diskIsBlockDevice(self.img).AndReturn(False)

    base.captureCall(['mount', '-o', 'loop', self.img, self.root])
    base.captureCall(['umount', '-l', self.root])

    self.mox.StubOutWithMock(os, 'rmdir')
    os.rmdir(self.root)

    self.mox.ReplayAll()

    deb = TestDebian()

    self.assertEqual(deb._mountImage(self.img), self.root)
    deb._umountImage(self.root)

  def testFailure(self):
    utils.diskIsBlockDevice(self.img).AndReturn(False)

    base.captureCall(
        ['mount', '-o', 'loop', self.img, self.root]).AndRaise(
        subprocess.CalledProcessError(
            2,
            ['mount', '-o', 'loop', self.img, self.root]))

    self.mox.StubOutWithMock(os, 'rmdir')
    os.rmdir(self.root)

    self.mox.ReplayAll()

    deb = TestDebian()

    self.assertRaises(subprocess.CalledProcessError,
                      deb._mountImage, self.img)


class TestDebianVerifyImage(mox.MoxTestBase):
  def setUp(self):
    super(TestDebianVerifyImage, self).setUp()

    self.mox.StubOutWithMock(debian.Debian, '_mountImage')
    self.mox.StubOutWithMock(base, 'captureCall')
    self.mox.StubOutWithMock(debian.Debian, '_umountImage')

    debian.Debian._mountImage('/home/evan/test.img').AndReturn('/tmp/tmp.ABC')

    debian.Debian._umountImage('/tmp/tmp.ABC')

  def testUpdateError(self):
    base.captureCall(['chroot', '/tmp/tmp.ABC', 'apt-get', '-qq', 'update']).\
        AndRaise(subprocess.CalledProcessError(1, []))

    self.mox.ReplayAll()

    self.assertEqual(TestDebian()._verifyImage('/home/evan/test.img'),
                     False)

  def testGood(self):
    base.captureCall(['chroot', '/tmp/tmp.ABC', 'apt-get', '-qq', 'update']).\
        AndReturn('')

    base.captureCall(['chroot', '/tmp/tmp.ABC', 'apt-get',
                      '-o', 'Debug::NoLocking=true',
                      '-sqq',
                      'dist-upgrade']).AndReturn('\n')

    self.mox.ReplayAll()

    self.assertEqual(TestDebian()._verifyImage('/home/evan/test.img'),
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

    self.assertEqual(TestDebian()._verifyImage('/home/evan/test.img'),
                     False)


class TestDebianVerify(mox.MoxTestBase):
  def setUp(self):
    super(TestDebianVerify, self).setUp()

    self.mox.StubOutWithMock(base.Distribution, 'verifyBase')
    self.mox.StubOutWithMock(base.Distribution, 'verifyCustom')
    self.mox.StubOutWithMock(debian.Debian, '_verifyImage')

  def testNoExists(self):
    base.Distribution.verifyBase().AndReturn(False)
    base.Distribution.verifyCustom().AndReturn(False)

    self.mox.ReplayAll()

    self.assertEqual(TestDebian().verifyBase(), False)
    self.assertEqual(
        TestDebian(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        False)

  def testExists(self):
    base.Distribution.verifyBase().AndReturn(True)
    base.Distribution.verifyCustom().AndReturn(True)

    debian.Debian._verifyImage(mox.IgnoreArg()).MultipleTimes().AndReturn(
        False)

    self.mox.ReplayAll()

    self.assertEqual(TestDebian().verifyBase(), False)
    self.assertEqual(
        TestDebian(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        False)

  def testAllGood(self):
    base.Distribution.verifyBase().AndReturn(True)
    base.Distribution.verifyCustom().AndReturn(True)

    debian.Debian._verifyImage(mox.IgnoreArg()).MultipleTimes().AndReturn(True)

    self.mox.ReplayAll()

    self.assertEqual(TestDebian().verifyBase(), True)
    self.assertEqual(
        TestDebian(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        True)


class TestDebianCreateSparseFile(unittest.TestCase):
  """Test creating sparse files.

  For once, this has well enough defined behavior that we can actually
  test ends instead of means.
  """
  def testCreateFile(self):
    fd, name = tempfile.mkstemp()
    os.close(fd)
    size = 1024 ** 2

    TestDebian()._createSparseFile(name, size)

    try:
      self.assertEqual(os.stat(name).st_size, size)
      self.assertEqual(os.stat(name).st_blocks, 0)
    finally:
      os.remove(name)

  def testCreateDirectoriesAndFile(self):
    dir = tempfile.mkdtemp()

    name = os.path.join(dir, 'foo/file')
    size = 1024 ** 2
    TestDebian()._createSparseFile(name, size)

    try:
      self.assertEqual(os.stat(name).st_size, size)
      self.assertEqual(os.stat(name).st_blocks, 0)
    finally:
      shutil.rmtree(dir)


class TestDebianRunInTarget(mox.MoxTestBase):
  def test(self):
    self.mox.StubOutWithMock(base, 'captureCall')

    base.captureCall(['chroot', 'foo', 'some', 'command'])

    self.mox.ReplayAll()

    deb = TestDebian()
    deb.target = 'foo'
    deb._runInTarget(['some', 'command'])


class TestDebianInstallFilesystem(mox.MoxTestBase):
  def test(self):
    fd, name = tempfile.mkstemp()
    os.close(fd)

    try:
      deb = TestDebian()
      deb._createSparseFile(name, 1024**3)
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


class TestDebianInstallSwap(unittest.TestCase):
  def test(self):
    fd, name = tempfile.mkstemp()
    os.close(fd)

    try:
      deb = TestDebian()
      deb._createSparseFile(name, 1024**3)
      deb._installSwap(name)

      # Test that what we ended up with is actually swapspace.
      fd = open(name)
      fd.seek(4086)
      self.assertEqual(fd.read(10), 'SWAPSPACE2')
    finally:
      os.remove(name)


class TestMethodsWithoutInitScripts(mox.MoxTestBase):
  """Superclass for testing methods wrapped in withoutInitScripts."""
  def setUp(self):
    super(TestMethodsWithoutInitScripts, self).setUp()

    self.mox.StubOutWithMock(debian, '_stopInitScripts')
    self.mox.StubOutWithMock(debian, '_startInitScripts')

    debian._stopInitScripts(mox.IgnoreArg())
    debian._startInitScripts(mox.IgnoreArg())


class TestDebianInstallPackage(TestMethodsWithoutInitScripts):
  def test(self):
    self.mox.StubOutWithMock(debian.Debian, '_runInTarget')

    env = dict(os.environ)
    env['DEBIAN_FRONTEND'] = 'noninteractive'
    debian.Debian._runInTarget(['apt-get', '-y', 'install', 'foo', 'bar'],
                               env=env)

    self.mox.ReplayAll()

    deb = TestDebian()
    deb.target = 'blah'
    deb._installPackages('foo', 'bar')


class TestDebianInstallReconfigure(TestMethodsWithoutInitScripts):
  def test(self):
    self.mox.StubOutWithMock(debian.Debian, '_runInTarget')

    debian.Debian._runInTarget(['dpkg-reconfigure',
                                '-fnoninteractive',
                                '-pcritical',
                                'foo'])

    self.mox.ReplayAll()

    deb = TestDebian()
    deb.target = 'blah'
    deb._installReconfigure('foo')


class TestDebianInstallDebootstrap(mox.MoxTestBase):
  def test(self):
    self.mox.StubOutWithMock(base, 'captureCall')

    deb = TestDebian()
    deb.target = 'blah'

    base.captureCall([
        'debootstrap',
        '--keyring=/usr/share/keyrings/debian-archive-keyring.gpg',
        '--arch=amd64',
        '--components=main,contrib,non-free',
        'lenny',
        'blah',
        'http://ftp.us.debian.org/debian/'])

    self.mox.ReplayAll()

    deb._installDebootstrap()


class TestDebianInstallHosts(unittest.TestCase):
  def test(self):
    target = tempfile.mkdtemp()
    hosts_dir = os.path.join(target, 'etc')
    os.mkdir(hosts_dir)

    try:
      deb = TestDebian()
      deb.target = target

      deb._installHosts()

      hosts = os.path.join(hosts_dir, 'hosts')
      self.assert_(os.path.exists(hosts))
      self.assert_(re.search('^127\.0\.0\.1\s+localhost',
                             open(hosts).read(),
                             re.M))
    finally:
      shutil.rmtree(target)


class TestDebianInstallSources(unittest.TestCase):
  def testNoComponents(self):
    target = tempfile.mkdtemp()
    sources_dir = os.path.join(target, 'etc/apt')
    os.makedirs(sources_dir)

    try:
      deb = TestDebian({'enable_security': False,
                        'enable_volatile': False})
      deb.target = target

      deb._installSources()

      sources_path = os.path.join(sources_dir, 'sources.list')
      sources = open(sources_path).read()

      self.assert_(re.search(
          '^deb http://ftp\.us\.debian\.org/debian/',
          sources,
          re.M))
      self.assert_(not re.search(
          '^deb http://security\.debian\.org/',
          sources,
          re.M))
      self.assert_(not re.search(
          '^deb http://volatile\.debian\.org/debian-volatile/',
          sources,
          re.M))
    finally:
      shutil.rmtree(target)

  def testAllComponents(self):
    target = tempfile.mkdtemp()
    sources_dir = os.path.join(target, 'etc/apt')
    os.makedirs(sources_dir)

    try:
      deb = TestDebian({'enable_security': True,
                        'enable_volatile': True})
      deb.target = target

      deb._installSources()

      sources_path = os.path.join(sources_dir, 'sources.list')
      sources = open(sources_path).read()

      self.assert_(re.search(
          '^deb http://ftp\.us\.debian\.org/debian/',
          sources,
          re.M))
      self.assert_(re.search(
          '^deb http://security\.debian\.org/',
          sources,
          re.M))
      self.assert_(re.search(
          '^deb http://volatile\.debian\.org/debian-volatile/',
          sources,
          re.M))
    finally:
      shutil.rmtree(target)


class TestDebianInstallUpdates(TestMethodsWithoutInitScripts):
  def test(self):
    self.mox.StubOutWithMock(debian.Debian, '_runInTarget')

    debian.Debian._runInTarget(['apt-get', 'update'])
    debian.Debian._runInTarget(['apt-get', '-y', 'dist-upgrade'])

    self.mox.ReplayAll()

    deb = TestDebian()
    deb.target = 'foo'
    deb._installUpdates()


class TestDebianInstallLocale(TestMethodsWithoutInitScripts):
  def test(self):
    target = tempfile.mkdtemp()
    etc_dir = os.path.join(target, 'etc')
    os.makedirs(etc_dir)

    defaults_dir = os.path.join(target, 'etc/default')
    os.makedirs(defaults_dir)

    try:
      self.mox.StubOutWithMock(debian.Debian, '_installPackages')
      self.mox.StubOutWithMock(debian.Debian, '_runInTarget')
      self.mox.StubOutWithMock(debian.Debian, '_installReconfigure')

      debian.Debian._installPackages('locales')
      debian.Debian._runInTarget(['locale-gen'])
      debian.Debian._installReconfigure('locales')

      self.mox.ReplayAll()

      deb = TestDebian()
      deb.target = target
      deb._installLocale()

      self.assertEqual(open(os.path.join(etc_dir, 'locale.gen')).read(),
                       'en_US.UTF-8 UTF-8\n')
      self.assertEqual(open(os.path.join(defaults_dir, 'locale')).read(),
                       'LANG="en_US.UTF-8"\n')
    finally:
      shutil.rmtree(target)


class TestDebianInstallTimezone(TestMethodsWithoutInitScripts):
  def test(self):
    target = tempfile.mkdtemp()
    etc_dir = os.path.join(target, 'etc')
    os.makedirs(etc_dir)

    try:
      self.mox.StubOutWithMock(debian.Debian, '_installReconfigure')
      debian.Debian._installReconfigure('tzdata')

      self.mox.ReplayAll()

      deb = TestDebian()
      deb.target = target
      deb._installTimezone()

      self.assertEqual(open(os.path.join(etc_dir, 'timezone')).read().strip(),
                       'America/Los_Angeles')
    finally:
      shutil.rmtree(target)


class TestDebianInstallPartitions(unittest.TestCase):
  def test(self):
    fd, name = tempfile.mkstemp()
    os.close(fd)
    size = 10 * (1024 ** 3)
    TestDebian()._createSparseFile(name, size)

    try:
      TestDebian()._installPartitions(name)

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


class TestDebianLoop(mox.MoxTestBase):
  def testSetup(self):
    self.mox.StubOutWithMock(base, 'captureCall')

    base.captureCall(['losetup', '--show', '--find', 'foo']).AndReturn(
        "/dev/loop0\n")

    self.mox.ReplayAll()

    self.assertEqual(TestDebian()._setupLoop('foo'), '/dev/loop0')

  def testCleanup(self):
    self.mox.StubOutWithMock(base, 'captureCall')

    base.captureCall(['losetup', '-d', '/dev/loop0'])

    self.mox.ReplayAll()

    TestDebian()._cleanupLoop('/dev/loop0')


class TestDebianDevices(mox.MoxTestBase):
  def testSetup(self):
    self.mox.StubOutWithMock(base, 'captureCall')

    base.captureCall(['kpartx', '-p', '', '-a', '/dev/loop0'])

    self.mox.ReplayAll()

    self.assertEqual(TestDebian()._setupDevices('/dev/loop0'),
                     '/dev/mapper/loop0')

  def testCleanup(self):
    self.mox.StubOutWithMock(base, 'captureCall')

    base.captureCall(['kpartx', '-p', '', '-d', '/dev/loop0'])

    self.mox.ReplayAll()

    TestDebian()._cleanupDevices('/dev/loop0')


class TestDebianCopyFilesystem(unittest.TestCase):
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

      TestDebian()._copyFilesystem(src, dst)

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


class TestDebianCreateBase(mox.MoxTestBase):
  def test(self):
    self.mox.StubOutWithMock(debian.Debian, 'verifyBase')
    self.mox.StubOutWithMock(debian.Debian, 'basePath')
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(os, 'remove')
    self.mox.StubOutWithMock(debian.Debian, '_createSparseFile')
    self.mox.StubOutWithMock(debian.Debian, '_installFilesystem')
    self.mox.StubOutWithMock(debian.Debian, '_mountImage')
    self.mox.StubOutWithMock(debian.Debian, '_installDebootstrap')
    self.mox.StubOutWithMock(debian.Debian, '_installHosts')
    self.mox.StubOutWithMock(debian.Debian, '_installSources')
    self.mox.StubOutWithMock(debian.Debian, '_installUpdates')
    self.mox.StubOutWithMock(debian.Debian, '_installLocale')
    self.mox.StubOutWithMock(debian.Debian, '_installTimezone')
    self.mox.StubOutWithMock(debian.Debian, '_umountImage')

    debian.Debian.verifyBase().AndReturn(True)

    debian.Debian.verifyBase().AndReturn(False)
    debian.Debian.basePath().MultipleTimes().AndReturn('abcd')
    os.path.exists('abcd').AndReturn(True)
    os.remove('abcd')

    debian.Debian._createSparseFile('abcd', 1024 ** 3)
    debian.Debian._installFilesystem('abcd')
    debian.Debian._mountImage('abcd').AndReturn('dcba')

    # The order these get called in does actually
    # matter. Unfortunately, we can't test that across multiple
    # MockMethods.
    debian.Debian._installDebootstrap()
    debian.Debian._installHosts()
    debian.Debian._installSources()
    debian.Debian._installUpdates()
    debian.Debian._installLocale()
    debian.Debian._installTimezone()
    debian.Debian._umountImage('dcba')

    self.mox.ReplayAll()

    # The first time we try, verifyBase returns True. Since the rest
    # of the method has only been stubbed out once, if returning True
    # doesn't cause us to return, then we'll throw errors about
    # methods being called too many times.
    TestDebian().createBase()
    TestDebian().createBase()


if __name__ == '__main__':
  unittest.main()
