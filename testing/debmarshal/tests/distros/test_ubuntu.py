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
import subprocess
import tempfile
import unittest

import mox

from debmarshal.distros import base
from debmarshal.distros import ubuntu


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

    deb = ubuntu.Ubuntu()

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

    deb = ubuntu.Ubuntu()

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

    self.assertEqual(ubuntu.Ubuntu()._verifyImage('/home/evan/test.img'),
                     False)

  def testGood(self):
    base.captureCall(['chroot', '/tmp/tmp.ABC', 'apt-get', '-qq', 'update']).\
        AndReturn('')

    base.captureCall(['chroot', '/tmp/tmp.ABC', 'apt-get',
                      '-o', 'Debug::NoLocking=true',
                      '-sqq',
                      'dist-upgrade']).AndReturn('\n')

    self.mox.ReplayAll()

    self.assertEqual(ubuntu.Ubuntu()._verifyImage('/home/evan/test.img'),
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

    self.assertEqual(ubuntu.Ubuntu()._verifyImage('/home/evan/test.img'),
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

    self.assertEqual(ubuntu.Ubuntu().verifyBase(), False)
    self.assertEqual(
        ubuntu.Ubuntu(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        False)

  def testExists(self):
    base.Distribution.verifyBase().AndReturn(True)
    base.Distribution.verifyCustom().AndReturn(True)

    ubuntu.Ubuntu._verifyImage(mox.IgnoreArg()).MultipleTimes().AndReturn(
        False)

    self.mox.ReplayAll()

    self.assertEqual(ubuntu.Ubuntu().verifyBase(), False)
    self.assertEqual(
        ubuntu.Ubuntu(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        False)

  def testAllGood(self):
    base.Distribution.verifyBase().AndReturn(True)
    base.Distribution.verifyCustom().AndReturn(True)

    ubuntu.Ubuntu._verifyImage(mox.IgnoreArg()).MultipleTimes().AndReturn(True)

    self.mox.ReplayAll()

    self.assertEqual(ubuntu.Ubuntu().verifyBase(), True)
    self.assertEqual(
        ubuntu.Ubuntu(
            None, {'hostname': 'www', 'domain': 'example.com'}).verifyCustom(),
        True)


if __name__ == '__main__':
  unittest.main()
