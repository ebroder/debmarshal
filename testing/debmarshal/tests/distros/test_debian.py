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
import struct
import subprocess
import tempfile
import unittest

import mox

from debmarshal.distros import base
from debmarshal.distros import debian
from debmarshal.tests.distros import test_base


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

  def testSuccess(self):
    base.captureCall(['mount', '-o', 'loop', self.img, self.root])
    base.captureCall(['umount', '-l', self.root])

    self.mox.StubOutWithMock(os, 'rmdir')
    os.rmdir(self.root)

    self.mox.ReplayAll()

    deb = TestDebian()

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


if __name__ == '__main__':
  unittest.main()
