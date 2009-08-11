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
"""Base for debmarshal's distribution representation classes."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import ConfigParser
import errno
import glob
import itertools
try:
  import hashlib as md5
except ImportError:  # pragma: no cover
  import md5
import os
import random
import shutil
import stat
import string
import subprocess
import tempfile

import pkg_resources

from debmarshal import errors


def _randomString():
  """Generate a random string.

  The specific random string generated is composed of upper- and
  lower-case ASCII characters and is 32 characters long, but that's
  just an implementational detail.

  The string will always be valid as a component of a file path.
  """
  return ''.join(random.choice(string.ascii_letters) for i in xrange(32))


def captureCall(popen_args, stdin_str=None, *args, **kwargs):
  """Capture stdout from a command.

  This method will proxy the arguments to subprocess.Popen. It returns
  the output from the command if the call succeeded and raises an
  exception if the process returns a non-0 value.

  This is intended to be a variant on the subprocess.check_call
  function that also allows you access to the output from the command.

  Args:
    popen_args: A string or sequence of program arguments. (The first
      argument to subprocess.Popen)
    stdin_str: A string to pass in on stdin. This requires the stdin
      kwarg to either be unset or subprocess.PIPE.
    All other arguments are the same as the arguments to subprocess.Popen

  Returns:
    Anything printed on stdout by the process.

  Raises:
    debmarshal.errors.CalledProcessError: Raised if the command
      returns non-0.
  """
  if 'stdin' not in kwargs:
    kwargs['stdin'] = subprocess.PIPE
  if 'stdout' not in kwargs:
    kwargs['stdout'] = subprocess.PIPE
  if 'stderr' not in kwargs:
    kwargs['stderr'] = subprocess.STDOUT
  p = subprocess.Popen(popen_args, *args, **kwargs)
  out, _ = p.communicate(stdin_str)
  if p.returncode:
    raise errors.CalledProcessError(p.returncode, popen_args, out)
  return out


def _createNewLoopDev():
  """Create a new loop device.

  On recent kernels (>2.6.22), the kernel actually supports a bunch of
  loop devices, but only creates nodes for /dev/loop0 through
  /dev/loop7 by default.

  We should be able to create more loop devices with just an
  appropriate mknod call.

  We need to try multiple times, just in case somebody else is running
  this at the same time.
  """
  while True:
    loop_nums = (int(loop[9:]) for loop in glob.glob('/dev/loop*'))
    last_loop = max(loop_nums)

    new_loop = last_loop + 1

    try:
      # TODO(ebroder): Figure out how to get udev to generate the /dev
      #   node. We want udev to be doing that so that all of the
      #   permissions get set correctly, etc.
      os.mknod('/dev/loop%d' % new_loop,
               stat.S_IFBLK | 0600,
               os.makedev(7, new_loop))
      break
    except EnvironmentError, e:
      if e.errno != errno.EEXIST:
        raise


def setupLoop(img):
  """Setup a loop device for a disk image.

  Args:
    img: Path to the image file.

  Returns:
    The image exposed as a block device.
  """
  # We have to try a few times just in case there's contention over
  # the newly created loop devices, but we also have to give up
  # eventually in case we're on an insufficiently new kernel
  for i in itertools.count(0):
    try:
      return captureCall(['losetup', '--show', '--find', img]).strip()
    except errors.CalledProcessError, e:
      if (e.output != 'losetup: could not find any free loop device\n' or
          i == 9):
        raise

      _createNewLoopDev()



def cleanupLoop(blk):
  """Clean up a loop device for a disk image.

  Args:
    blk: The block device returned from setupLoop
  """
  captureCall(['losetup', '-d', blk])


def createSparseFile(path, len):
  """Create a sparse file.

  Create a sparse file with a given length, say for use as a disk
  image.

  It is the caller's responsibility to ensure that the passed in path
  doesn't exist, or can be overwritten.

  Args:
    path: Path to the file to be created.
    len: Length of the sparse file in bytes.
  """
  dir = os.path.dirname(path)
  if not os.path.exists(dir):
    os.makedirs(dir)
  open(path, 'w').truncate(len)


def createCow(path, size):
  """Create a copy-on-write snapshot of a device.

  This will use the device-mapper to create a copy-on-write snapshot
  of a block device.

  It is the caller's responsibility to ensure that no writes to the
  origin device occur after the snapshot is created.

  Args:
    path: The path to the block device to use as the snapshot origin.
    size: The amount of space to allocate for the copy-on-write volume
      in bytes. This does not have to be as large as the origin
      volume, and is frequently much smaller.

  Returns:
    A path to the new copy-on-write snapshot device.
  """
  # Unfortunately, the only option for a dynamically-sized,
  # nonpersistent block device is a loop device backed by a sparse
  # file on a tmpfs.
  #
  # Especially if you want the copy-on-write device to be swappable,
  # which you probably do, since you could potentially have gigabytes
  # of RAM tied up in these CoW volumes.
  #
  # RAM disks (i.e. /dev/ram*) aren't an option because there's a
  # fixed number of them, they don't swap, and their size is fixed at
  # boot.
  cowdir = tempfile.mkdtemp()

  try:
    captureCall(['mount',
                 '-t', 'tmpfs',
                 '-o', 'size=%d' % size,
                 'tmpcow',
                 cowdir])
    try:
      cow_path = os.path.join(cowdir, 'cowfile')
      createSparseFile(cow_path, size)
      cow_loop = setupLoop(cow_path)

      try:
        origin_size = captureCall(['blockdev', '--getsz', path]).strip()

        table = '0 %s snapshot %s %s N 128' % (
          origin_size,
          path,
          cow_loop)

        while True:
          try:
            name = _randomString()
            captureCall(['dmsetup', 'create', name], stdin_str=table)
            return os.path.join('/dev/mapper', name)
          except errors.CalledProcessError, e:
            if not e.output.startswith(
              'device-mapper: create ioctl failed: Device or resource busy'):
              raise

      # Only want to undo the loop in case of failure
      except:
        cleanupLoop(cow_loop)
        raise
    finally:
      captureCall(['umount', '-l', cowdir])
  finally:
    shutil.rmtree(cowdir)


def cleanupCow(path):
  """Cleanup a snapshot device.

  Args:
    path: The path to the copy-on-write block device.
  """
  table = captureCall(['dmsetup', 'table', path])

  origin, cow = table.split()[3:5]
  assert cow.split(':')[0] == '7'

  captureCall(['dmsetup', 'remove', path])
  cleanupLoop('/dev/loop%s' % cow.split(':')[1])


def findDistribution(name):
  """Find an installed distribtion.

  Args:
    name: The name of the distribution to use. This should be the name
      of an entry_point providing debmarshal.distributions

  Returns:
    The class providing the entry_point of the given name.
  """
  entry_points = list(pkg_resources.iter_entry_points(
      'debmarshal.distributions',
      name=name))
  assert len(entry_points) == 1

  return entry_points.pop().load()


class DistributionMeta(type):
  """Metaclass for Distribution classes.

  This class handles any metaprogramming magic that needs to happen
  for Distribution classes to work right.

  So far that means generating the version variable by chaining
  together the version strings for all parent classes, giving a
  representation of the version that reflects changes in both the
  Distribution subclass, and in all parent classes.
  """
  def __init__(cls, name, bases, dct):
    """Coalesce a version number for a Distribution class.

    This will work out to be a series of fairly heavily nested
    tuples. For example, if Dist3 subclasses Dist2 subclasses Dist1,
    then Dist3.version will be (Dist3._version, (Dist2._version,
    (Dist1._version,))).

    Ugly? Kind of. But easy to keep consistent.
    """
    super(DistributionMeta, cls).__init__(name, bases, dct)

    cls.version = ((cls._version,) +
                   tuple(b.version for b in bases if hasattr(b, 'version')))


# TODO(ebroder): Look into using protocol buffers instead of this
#   hackish configuration solution
class Distribution(object):
  """Superclass representation of an abstract Linux distribution.

  Classes derived from Distribution represent Linux distributions and
  the mechanism by which one can be installed/imaged.

  The code and comments refer a lot to Linux distributions.  This
  class could potentially be used for any operating system for which
  an unattended install is possible, although whether it can be booted
  depends a lot on the specific virtualization technology being used.

  For a distribution install, there are two stages. The first stage
  installs a completely uncustomized base OS; the second customizes
  the base image for use with a particular test case.

  Both stages can have a set of configuration options, some of which
  can be set by users of the distribution class, some which can't be,
  and some which must be. Together, these options can be used to
  uniquely identify a given snapshot.

  Options with defaults can be overridden using an
  /etc/debmarshal/distros.conf configuration file.

  Attributes:
    base_defaults: A dict with the default configuration options for
      the base image.
    base_configurable: A set of option names that can be set by users
      of the distribution. Any elements which aren't also defined in
      base_defaults must be passed in by the user.
    custom_defaults: The default configuration options for the stage
      2 image.
    custom_configurable: The set of option names that can be set by
      users for stage 2. Any elements which aren't also defined in
      custom_defaults must be passed in by the user.
    _name: A short, unique name for the Distribution subclass. This
      should be the same as the name of a debmarshal.distributions
      entry_point directed at the subclass.
    _version: A version number for the distribution generator. This
      should be uniquely tracked by each Distribution subclass, and
      incremented whenever changes to the Distribution subclass would
      affect the generated images.
  """
  __metaclass__ = DistributionMeta

  _version = 1

  _base_hash = None

  _custom_hash = None

  def _initDefaults(self):
    """Initialize the defaults and configurable options."""
    self.base_defaults = {}

    self.base_configurable = set()

    self.custom_defaults = {}

    self.custom_configurable = set()

  def _updateDefaults(self):
    parser = ConfigParser.SafeConfigParser()
    parser.read(['/etc/debmarshal/distros.conf'])
    if parser.has_section(self._name + '.base'):
      self.base_defaults.update(
          (k, v) for k, v in
          parser.items(self._name + '.base')
          if k in self.base_defaults and
          isinstance(self.base_defaults[k], basestring))

    if parser.has_section(self._name + '.custom'):
      self.custom_defaults.update(
          (k, v) for k, v in
          parser.items(self._name + '.custom')
          if k in self.custom_defaults and
          isinstance(self.custom_defaults[k], basestring))

  def __init__(self, base_config=None, custom_config=None):
    """Instantiate and configure a distribution.

    Both base_config and custom_config can be None, but if they are
    not, they will be validated against the appropriate _defaults and
    _configurable attributes.

    Args:
      base_config: If not None, a dict with configuration for the
        distribution base image.
      custom_config: If not None, a dict with configuration for the
        customization of the base image.
    """
    self._initDefaults()
    self._updateDefaults()

    if base_config is not None:
      base_keys = set(base_config)
      base_def_keys = set(self.base_defaults)
      missing = self.base_configurable - base_def_keys - base_keys
      if missing:
        raise errors.InvalidInput(
            "Missing required base_config settings: %s" % missing)
      extra = base_keys - self.base_configurable
      if extra:
        raise errors.InvalidInput(
            "Extra base_config settings passed in: %s" % extra)

      self.base_config = base_config
    else:
      self.base_config = {}

    if custom_config is not None:
      custom_keys = set(custom_config)
      custom_def_keys = set(self.custom_defaults)
      missing = self.custom_configurable - custom_def_keys - custom_keys
      if missing:
        raise errors.InvalidInput(
            "Missing required custom_config settings: %s" % missing)
      extra = custom_keys - self.custom_configurable
      if extra:
        raise errors.InvalidInput(
            "Extra custom_config settings passed in: %s" % extra)

      self.custom_config = custom_config
    else:
      self.custom_config = {}

  def getBaseConfig(self, key):
    """Get a base image config value.

    This first checks the instance-level customizations for the base
    image, falling back on global defaults.

    If the key is not present in either dict, looking up that key in
    the default dict will raise a KeyError.

    Args:
      key: The key to lookup

    Returns:
      The corresponding value for the key, if it is present in either
        the local customizations or the global defaults.
    """
    if key in self.base_config:
      return self.base_config[key]
    else:
      return self.base_defaults[key]

  def getCustomConfig(self, key):
    """Get a customized image config value.

    This first checks the instance-level customizations for the
    customized image, falling back on global defaults.

    If the key is not present in either dict, looking up that key in
    the default dict will raise a KeyError.

    Args:
      key: The key to lookup

    Returns:
      The corresponding value for the key, if it is present in either
        the local customizations or the global defaults.
    """
    if key in self.custom_config:
      return self.custom_config[key]
    else:
      return self.custom_defaults[key]

  def hashBaseConfig(self):
    """Return a hashed representation of the Distribution base config.

    This function returns a string hash for this Distribution
    instance. For any two Distribution objects that would generate the
    same base image, the base config hash should be the same; for any
    two that would generate a different base image, the hash should be
    different (modulo hash collisions).

    Settings in base_defaults that can't be overridden by the user
    shouldn't affect the resulting image, so they're ignored for
    purposes of calculating the hash.

    Returns:
      A hash corresponding to this particular Distribution
        base configuration.
    """
    if not self._base_hash:
      elements_to_hash = (
        self._name,
        self.version,
        tuple(sorted(
            (k, self.getBaseConfig(k)) for k in self.base_configurable)),
        )
      self._base_hash = md5.md5(repr(elements_to_hash)).hexdigest()
    return self._base_hash

  def hashConfig(self):
    """Return a hashed representation of the Distribution config.

    This function returns a string hash for this Distribution
    instance. For any two Distribution objects that would generate the
    same customized image, the config hash should be the same; for any
    two that would generate a different customized image, the hash
    should be different (modulo hash collisions).

    Settings in base_defaults and custom_defaults that can't be
    overridden by the user shouldn't affect the resulting image, so
    they're ignored for purposes of calculating the hash.

    Returns:
      A hash corresponding to this particular Distribution
        configuration.
    """
    if not self._custom_hash:
      elements_to_hash = (
        self.hashBaseConfig(),
        tuple(sorted(
            (k, self.getCustomConfig(k)) for k in self.custom_configurable)),
        )
      self._custom_hash = md5.md5(repr(elements_to_hash)).hexdigest()
    return self._custom_hash

  def basePath(self):
    """Return the path where the base image is cached.

    Subclasses of Distribution can use this path however they want. It
    can be a tarball, or a filesystem image, or whatever. But it has
    to go here.

    Returns:
      The filesystem path where the base image is stored for this
        distribution with this configuration.
    """
    return os.path.join('/var/cache/debmarshal/images/base',
                        self.hashBaseConfig())

  def customPath(self):
    """Return the path where the custom image is cached.

    Like the basePath, the cache of a custom image must go here if
    it's going to be cached.

    Returns:
      The filesystem path where the customized image is stored for
        this distribution with this configuration.
    """
    return os.path.join('/var/cache/debmarshal/images/custom',
                        self.hashConfig())

  def verifyBase(self):
    """Verify that a base image is still valid.

    This method is responsible for verifying that the base image for
    this configuration still exists, and is still valid.

    In the Distribution class, this means verifying the existence of a
    base image. Subclasses might want to do checks such as if there
    are any available package updates.

    Returns:
      A bool. True if the image is valid; False if it's not.
    """
    return os.path.exists(self.basePath())

  def verifyCustom(self):
    """Verify that a customized image is still valid.

    This method is responsible for verifying that the custom image for
    this configuration still exists, and is still valid.

    If this method is called, then the base image from which this
    custom image was generated has already been verified.

    In the Distribution class, the existence of the custom image is
    verified. Subclasses might want to do checks such as if there are
    package updates available.

    Returns:
      A bool. True if the image is valid; False if it's not.
    """
    return os.path.exists(self.customPath())

  def createBase(self):
    """Create a valid base image.

    This method is responsible for creating a base image at
    self.basePath().

    No arguments are taken and no value is returned, because the
    location of the resulting base image is already known.

    This method should be overridden in subclasses.
    """
    raise errors.NotImplementedError

  def createCustom(self):
    """Create a valid customized image.

    This method is responsible for creating a customized image at
    self.customPath().

    No arguments are taken and no value is returned, because the
    location of the resulting image is already known.

    This method should be overridden in subclasses.
    """
    raise errors.NotImplementedError

  def baseCow(self, size):
    """Create a memory-backed snapshot of the base image.

    Args:
      size: Size of the snapshot volume, in bytes.
    """
    loop = setupLoop(self.basePath())
    return createCow(loop, size)

  def customCow(self, size):
    """Create a memory-backed snapshot of the custom image.

    Args:
      size: Size of the snapshot volume, in bytes.
    """
    loop = setupLoop(self.customPath())
    return createCow(loop, size)
