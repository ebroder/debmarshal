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
import subprocess
import tempfile
import unittest

import mox

from debmarshal.distros import base
from debmarshal.distros import debian


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
    self.assertEqual(debian.Debian().custom_defaults['kernel'],
                     'linux-image-amd64')
    self.assertEqual(debian.Debian({'arch': 'arm'}).custom_defaults['kernel'],
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

    deb = debian.Debian()

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

    deb = debian.Debian()

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

    self.assertEqual(debian.Debian()._verifyImage('/home/evan/test.img'),
                     False)

  def testGood(self):
    base.captureCall(['chroot', '/tmp/tmp.ABC', 'apt-get', '-qq', 'update']).\
        AndReturn('')

    base.captureCall(['chroot', '/tmp/tmp.ABC', 'apt-get',
                      '-o', 'Debug::NoLocking=true',
                      '-sqq',
                      'dist-upgrade']).AndReturn('\n')

    self.mox.ReplayAll()

    self.assertEqual(debian.Debian()._verifyImage('/home/evan/test.img'),
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

    self.assertEqual(debian.Debian()._verifyImage('/home/evan/test.img'),
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

    self.assertEqual(debian.Debian().verifyBase(), False)
    self.assertEqual(
        debian.Debian(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        False)

  def testExists(self):
    base.Distribution.verifyBase().AndReturn(True)
    base.Distribution.verifyCustom().AndReturn(True)

    debian.Debian._verifyImage(mox.IgnoreArg()).MultipleTimes().AndReturn(
        False)

    self.mox.ReplayAll()

    self.assertEqual(debian.Debian().verifyBase(), False)
    self.assertEqual(
        debian.Debian(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        False)

  def testAllGood(self):
    base.Distribution.verifyBase().AndReturn(True)
    base.Distribution.verifyCustom().AndReturn(True)

    debian.Debian._verifyImage(mox.IgnoreArg()).MultipleTimes().AndReturn(True)

    self.mox.ReplayAll()

    self.assertEqual(debian.Debian().verifyBase(), True)
    self.assertEqual(
        debian.Debian(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        True)


if __name__ == '__main__':
  unittest.main()
