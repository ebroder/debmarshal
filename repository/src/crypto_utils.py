#!/usr/bin/python2.4
#
# Copyright 2006 Google Inc. All Rights Reserved.

"""Cryptographic utility functions

The crypto_utils module contains utility functions that deal with
cryptographic hash and digital signatures needed for package
verification and release publishing procedures.
"""

__author__ = 'cklin@google.com (Chuan-Kai Lin)'

import logging as lg
import os
import subprocess as sp
import os_utils as ou


def VerifyMD5Hash(md5_dict):
  """Verify the MD5 hash value of a list of files

  This function accepts a dictionary that maps file names to their MD5
  hash values (as hexadecimal strings) and verifies that those files
  have the expected MD5 hash values.  It does so by writing the MD5
  information to a temporary file and invoking the md5sum program.
  """

  def DoVerify(md5_file, fobj):
    for name in md5_dict:
      fobj.write(md5_dict[name]+'  '+name+'\n')
    fobj.close()
    if ou.SpawnProgram(['/usr/bin/md5sum', '-c', md5_file]):
      lg.error('MD5 hash validation failed')
      raise EnvironmentError

  ou.RunWithTempFile(DoVerify)


def GetMD5Hash(name):
  """Compute the MD5 hash value of a file as a hex string
  """

  args = ['/usr/bin/md5sum', name]
  child = sp.Popen(args, stdout=sp.PIPE, stderr=sp.PIPE)
  child.wait()
  line = child.stdout.readline()
  if not line:
    lg.error(child.stderr.readline())
    raise ValueError
  return line.split()[0]


def GetSHA1Hash(name):
  """Compute the SHA1 hash value of a file as a hex string
  """

  args = ['/usr/bin/sha1sum', name]
  child = sp.Popen(args, stdout=sp.PIPE, stderr=sp.PIPE)
  child.wait()
  line = child.stdout.readline()
  if not line:
    lg.error(child.stderr.readline())
    raise ValueError
  return line.split()[0]


def VerifySignature(name):
  """Verify embedded signature in a file with gpgv
  """

  if ou.SpawnProgram(['/usr/bin/gpgv', name]):
    lg.error('Cannot verify signature in file ' + name)
    raise EnvironmentError


def MakeReleaseSignature(name):
  """Make a detached signature file with .gpg extension
  """

  ou.SpawnProgram(['/usr/bin/gpg', '--use-agent', '-a', '-b', name])
  try:
    os.rename(name + '.asc', name + '.gpg')
  except OSError:
    lg.error('Fail to complete release signing operation')
