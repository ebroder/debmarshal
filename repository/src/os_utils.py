#!/usr/bin/python2.4
#
# Copyright 2006 Google Inc. All Rights Reserved.

"""Operating system and file operation utilities

The os_utils module contains utility functions for common operating
system and file operations in debmarshal.  To achieve better
generality, many utility functions are higher-order functions that
supply additional input to existing functions.
"""

__author__ = 'cklin@google.com (Chuan-Kai Lin)'

import fileinput
import logging as lg
import os
import subprocess as sp
import shutil
import tarfile
import tempfile


def IgnoreOSError(func, param):
  """Call a single-parameter function and ignore OSError
  """

  try:
    return func(param)
  except OSError:
    pass


def RunInTempDir(func):
  """Run the given function in a secure temporary directory
  """

  current_dir = os.getcwd()
  temp_dir = tempfile.mkdtemp()
  try:
    os.chdir(temp_dir)
    return func()
  finally:
    os.chdir(current_dir)
    shutil.rmtree(temp_dir, True)


def RunWithTempFile(func):
  """Run the given function in a secure temporary file
  """

  fd, name = tempfile.mkstemp()
  fobj = os.fdopen(fd, 'w')
  try:
    return func(name, fobj)
  finally:
    fobj.close()
    IgnoreOSError(os.remove, name)


def RunWithFileInput(func, name):
  """Run the given function with the contents of a file
  """

  finput = fileinput.input(name)
  try:
    try:
      return func(finput)
    except IOError, mesg:
      lg.error(str(mesg))
  finally:
    finput.close()


def RunWithTarInput(func, name):
  """Run the given function with a tarball as input

  This function tries to open a tarball (with various optional
  suffixes) and pass the TarFile object as the argument to another
  function.  RunWithTarInput() closes the TarFile object before
  returning to the caller.
  """

  suffixes = ['', '.tar', '.tar.gz', '.tar.bz2']

  for suffix in suffixes:
    if os.path.isfile(name + suffix):
      name = name + suffix
      break
  if not os.path.isfile(name):
    lg.error('Cannot open tar file ' + name)
    raise IOError

  tar = tarfile.open(name)
  try:
    return func(tar)
  finally:
    tar.close()


def SpawnProgram(args):
  """Run an external program in a separate process

  This function takes an argument list (whose 0th element is the
  program to run), runs the program with the supplied arguments,
  redirect stdout and stderr to the logger (at INFO level), and
  returns the exit code of the program run.  The external program
  invocation does not go through the shell, so we are safe against
  command injection attacks.
  """

  child = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT)
  retval = child.wait()
  for line in child.stdout:
    lg.info(line.rstrip('\n'))
  return retval


def CopyDeleteFiles(dir_from, dir_to, file_list):
  """Move a list of files from one directory to another

  This function implements rename(2)-like functionality with a
  slightly more convenient interface.  It copies each file and then
  remove the original, so that the rename works across filesystems,
  and that a process holding an open file descriptor on the original
  cannot change the renamed copy.
  """

  if not os.path.exists(dir_to):
    os.makedirs(dir_to, 0755)

  path_from = ''
  try:
    for name in file_list:
      path_from = os.path.join(dir_from, name)
      path_to = os.path.join(dir_to, name)
      if name.find('/') >= 0:
        lg.error('File name ' + name + ' contains / character')
        raise ValueError
      shutil.copyfile(path_from, path_to)
      IgnoreOSError(os.remove, path_from)
  except IOError:
    lg.error('Cannot move file ' + path_from)
    raise
