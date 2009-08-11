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


import os
import re
import shutil
import struct
import subprocess
import tempfile
import unittest

import mox

from debmarshal.distros import base
from debmarshal.distros import ubuntu
from debmarshal.tests.distros import test_base


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


class TestUbuntuMountImage(mox.MoxTestBase):
  def setUp(self):
    super(TestUbuntuMountImage, self).setUp()

    self.img = '/home/ebroder/test.img'
    self.root = '/tmp/tmpABCDEF'

    self.mox.StubOutWithMock(tempfile, 'mkdtemp')
    tempfile.mkdtemp().AndReturn(self.root)

    self.mox.StubOutWithMock(base, 'captureCall')

  def testSuccess(self):
    base.captureCall(['mount', '-o', 'loop', self.img, self.root])
    base.captureCall(['umount', '-l', self.root])

    self.mox.StubOutWithMock(os, 'rmdir')
    os.rmdir(self.root)

    self.mox.ReplayAll()

    deb = TestUbuntu()

    self.assertEqual(deb._mountImage(self.img), self.root)
    deb._umountImage(self.root)

  def testFailure(self):
    base.captureCall(
        ['mount', '-o', 'loop', self.img, self.root]).AndRaise(
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

    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_mountImage')
    self.mox.StubOutWithMock(base, 'captureCall')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_umountImage')

    ubuntu.Ubuntu._mountImage('/home/evan/test.img').AndReturn('/tmp/tmp.ABC')

    ubuntu.Ubuntu._umountImage('/tmp/tmp.ABC')

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


class TestUbuntuVerify(mox.MoxTestBase):
  def setUp(self):
    super(TestUbuntuVerify, self).setUp()

    self.mox.StubOutWithMock(base.Distribution, 'verifyBase')
    self.mox.StubOutWithMock(base.Distribution, 'verifyCustom')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_verifyImage')

  def testNoExists(self):
    base.Distribution.verifyBase().AndReturn(False)
    base.Distribution.verifyCustom().AndReturn(False)

    self.mox.ReplayAll()

    self.assertEqual(TestUbuntu().verifyBase(), False)
    self.assertEqual(
        TestUbuntu(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        False)

  def testExists(self):
    base.Distribution.verifyBase().AndReturn(True)
    base.Distribution.verifyCustom().AndReturn(True)

    ubuntu.Ubuntu._verifyImage(mox.IgnoreArg()).MultipleTimes().AndReturn(
        False)

    self.mox.ReplayAll()

    self.assertEqual(TestUbuntu().verifyBase(), False)
    self.assertEqual(
        TestUbuntu(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        False)

  def testAllGood(self):
    base.Distribution.verifyBase().AndReturn(True)
    base.Distribution.verifyCustom().AndReturn(True)

    ubuntu.Ubuntu._verifyImage(mox.IgnoreArg()).MultipleTimes().AndReturn(True)

    self.mox.ReplayAll()

    self.assertEqual(TestUbuntu().verifyBase(), True)
    self.assertEqual(
        TestUbuntu(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        True)


class TestUbuntuCreateSparseFile(unittest.TestCase):
  """Test creating sparse files.

  For once, this has well enough defined behavior that we can actually
  test ends instead of means.
  """
  def testCreateFile(self):
    fd, name = tempfile.mkstemp()
    os.close(fd)
    size = 1024 ** 2

    TestUbuntu()._createSparseFile(name, size)

    try:
      self.assertEqual(os.stat(name).st_size, size)
      self.assertEqual(os.stat(name).st_blocks, 0)
    finally:
      os.remove(name)

  def testCreateDirectoriesAndFile(self):
    dir = tempfile.mkdtemp()

    name = os.path.join(dir, 'foo/file')
    size = 1024 ** 2
    TestUbuntu()._createSparseFile(name, size)

    try:
      self.assertEqual(os.stat(name).st_size, size)
      self.assertEqual(os.stat(name).st_blocks, 0)
    finally:
      shutil.rmtree(dir)


class TestUbuntuRunInTarget(mox.MoxTestBase):
  def test(self):
    self.mox.StubOutWithMock(base, 'captureCall')

    base.captureCall(['chroot', 'foo', 'some', 'command'])

    self.mox.ReplayAll()

    deb = TestUbuntu()
    deb.target = 'foo'
    deb._runInTarget(['some', 'command'])


class TestUbuntuInstallFilesystem(mox.MoxTestBase):
  def test(self):
    fd, name = tempfile.mkstemp()
    os.close(fd)

    try:
      deb = TestUbuntu()
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

    ubuntu.Ubuntu._runInTarget(['apt-get', 'update'])
    ubuntu.Ubuntu._runInTarget(['apt-get', '-y', 'dist-upgrade'])

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
  def test(self):
    target = tempfile.mkdtemp()
    etc_dir = os.path.join(target, 'etc')
    os.makedirs(etc_dir)

    try:
      self.mox.StubOutWithMock(ubuntu.Ubuntu, '_installReconfigure')
      ubuntu.Ubuntu._installReconfigure('tzdata')

      self.mox.ReplayAll()

      deb = TestUbuntu()
      deb.target = target
      deb._installTimezone()

      self.assertEqual(open(os.path.join(etc_dir, 'timezone')).read().strip(),
                       'America/Los_Angeles')
    finally:
      shutil.rmtree(target)


class TestUbuntuCreateBase(mox.MoxTestBase):
  def setUp(self):
    super(TestUbuntuCreateBase, self).setUp()

    self.mox.StubOutWithMock(ubuntu.Ubuntu, 'verifyBase')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, 'basePath')
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(os, 'remove')
    self.mox.StubOutWithMock(ubuntu.Ubuntu, '_createSparseFile')
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

    ubuntu.Ubuntu._createSparseFile('abcd', 1024 ** 3)
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


if __name__ == '__main__':
  unittest.main()
