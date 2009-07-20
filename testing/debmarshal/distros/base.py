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


try:
  import hashlib as md5
except ImportError:  # pragma: no cover
  import md5
import os
import subprocess

from debmarshal import errors


def captureCall(*args, **kwargs):
  """Capture stdout from a command.

  This method will proxy the arguments to subprocess.Popen. It returns
  the output from the command if the call succeeded and raises an
  exception if the process returns a non-0 value.

  This is intended to be a variant on the subprocess.check_call
  function that also allows you access to the output from the command.

  Args:
    All arguments are the same as the arguments to subprocess.Popen

  Returns:
    Anything printed on stdout by the process.

  Raises:
    subprocess.CalledProcessError: Raised if the command returns
      non-0.
  """
  if 'stdin' not in kwargs:
    kwargs['stdin'] = subprocess.PIPE
  if 'stdout' not in kwargs:
    kwargs['stdout'] = subprocess.PIPE
  if 'stderr' not in kwargs:
    kwargs['stderr'] = subprocess.STDOUT
  p = subprocess.Popen(*args, **kwargs)
  out, _ = p.communicate()
  if p.returncode:
    raise subprocess.CalledProcessError(p.returncode, args[0])
  return out


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
    _version: A version number for the distribution generator. This
      should be uniquely tracked by each Distribution subclass, and
      incremented whenever changes to the Distribution subclass would
      affect the generated images.
  """
  __metaclass__ = DistributionMeta

  base_defaults = {}

  base_configurable = set()

  custom_defaults = {}

  custom_configurable = set()

  _version = 1

  _base_hash = None

  _custom_hash = None

  @classmethod
  def classId(cls):
    """Identify this class by its full module path."""
    return '.'.join([cls.__module__, cls.__name__])

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
        self.classId(),
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
