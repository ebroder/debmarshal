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
"""Debmarshal distribution class for Ubuntu images."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import os
import shutil
import stat
import string
import subprocess
import tempfile

import decorator

from debmarshal.distros import base
from debmarshal import errors
from debmarshal import utils


def _stopInitScripts(target):
  """Stop init scripts from running.

  This function, along with _startInitScripts, primarily exists to
  allow for more easily mocking out the withoutInitScripts decorator
  in testing.

  Args:
    target: The root of the filesystem where we're stopping init
      scripts.
  """
  policy_path = os.path.join(target, 'usr/sbin/policy-rc.d')
  policy = open(policy_path, 'w')
  policy.write("#!/bin/sh\n"
               "exit 101\n")
  policy.close()

  os.chmod(policy_path, 0755)


def _startInitScripts(target):
  """Allow init scripts to write.

  This function, along with _stopInitScripts, primarily exists to
  allow for more easily mocking out the withoutInitScripts decorator
  in testing.

  Args:
    target: The root of the filesystem where we're allowing init
      scripts.
  """
  policy_path = os.path.join(target, 'usr/sbin/policy-rc.d')
  if os.path.exists(policy_path):
    os.remove(policy_path)


@decorator.decorator
def withoutInitScripts(f, *args, **kwargs):
  """Decorator to disable init scripts in a chroot.

  Functions decorated with withoutInitScripts have a policy.rc-d file
  created in order to prevent any Ubuntu Policy-compliant init scripts
  from running.

  This decorator is designed for use with class methods, and assumes
  that the object being operated on has a target attribute with the
  root of the disk image.
  """
  self = args[0]
  _stopInitScripts(self.target)

  try:
    f(*args, **kwargs)
  finally:
    _startInitScripts(self.target)


class Ubuntu(base.Distribution):
  """Ubuntu (and Ubuntu-based) distributions."""
  def _initDefaults(self):
    """Configure the settings defaults for Ubuntu distributions."""
    super(Ubuntu, self)._initDefaults()

    self.base_defaults.update({
        'mirror': 'http://us.archive.ubuntu.com/ubuntu/',
        'security_mirror': 'http://security.ubuntu.com/ubuntu/',
        'updates_mirror': 'http://us.archive.ubuntu.com/ubuntu/',
        'backports_mirror': 'http://us.archive.ubuntu.com/ubuntu/',
        'proposed_mirror': 'http://us.archive.ubuntu.com/ubuntu/',
        'enable_security': True,
        'enable_updates': True,
        'enable_backports': False,
        'enable_proposed': False,
        'keyring': '/usr/share/keyrings/ubuntu-archive-keyring.gpg',
        'arch': 'amd64',
        'suite': 'jaunty',
        'components': ['main', 'restricted', 'universe', 'multiverse']
        })

    self.base_configurable.update([
        'arch', 'suite', 'components', 'enable_security',
        'enable_updates', 'enable_backports',
        'enable_proposed'])

    self.custom_defaults.update({
        'add_pkg': [],
        'rm_pkg': [],
        'ssh_key': '',
        'kernel': 'linux-image-generic',
        # Configuration for networking doesn't really fit well into
        # this config model. But if dhcp is True, then ip, netmask,
        # gateway, and dns should have their default values. If dhcp
        # is False, then they should all be set.
        'dhcp': True,
        'ip': None,
        'netmask': None,
        'gateway': None,
        'dns': [],
        })

    self.custom_configurable.update([
        'add_pkg', 'rm_pkg', 'ssh_key', 'kernel',
        'hostname', 'domain',
        'dhcp', 'ip', 'netmask', 'gateway', 'dns'])

  def _mountImage(self, img):
    """Mount a filesystem image in a temporary directory.

    This method handles safely creating a location to mount an
    image. It is the responsibility of the caller to unmount an
    image. The use of _umountImage is recommended for handling this.

    Args:
      img: A filesystem image file.

    Returns:
      The root of the mounted filesystem.
    """
    root = tempfile.mkdtemp()
    try:
      args = ['mount']
      if not utils.diskIsBlockDevice(img):
        args.extend(('-o', 'loop'))
      args.extend((img, root))
      base.captureCall(args)
    except:
      os.rmdir(root)
      raise
    return root

  def _umountImage(self, root):
    """Clean up a temporarily mounted filesystem image.

    This method handles cleaning up after _mountImage.

    Args:
      root: The root of the temporary filesystem; the return value
        from _mountImage
    """
    base.captureCall(['umount', '-l', root])

    os.rmdir(root)

  def _verifyImage(self, image):
    """Verify that some disk image is still valid.

    For Ubuntu images, this means verifying that there are no pending
    package updates.

    This method is used for verifying both base and customized images.

    Args:
      image: The disk image file to verify.

    Returns:
      A bool. True if the image is valid; False if it's not.
    """
    root = self._mountImage(image)

    try:
      try:
        base.captureCall(['chroot', root,
                          'apt-get',
                          '-qq',
                          'update'])

        # apt-get -sqq dist-upgrade will print out a summary of the
        # steps it would have taken, had this not been a dry run. If
        # there is nothing to do, it will print nothing.
        updates = base.captureCall(['chroot', root,
                                    'apt-get',
                                    '-o', 'Debug::NoLocking=true',
                                    '-sqq',
                                    'dist-upgrade'])
        return updates.strip() == ''
      except subprocess.CalledProcessError:
        return False
    finally:
      self._umountImage(root)

  def verifyBase(self):
    """Verify that a base image is still valid.

    For Ubuntu images, this means verifying that there are no pending
    package updates.

    Returns:
      A bool. True if the image is valid; False if it's not.
    """
    if not super(Ubuntu, self).verifyBase():
      return False
    else:
      return self._verifyImage(self.basePath())

  def verifyCustom(self):
    """Verify that a customized image is still valid.

    For Ubuntu images, this means verifying that there are no pending
    package updates.

    Returns:
      A bool. True if the image is valid; False if it's not.
    """
    if not super(Ubuntu, self).verifyCustom():
      return False
    else:
      try:
        try:
          loop = self._setupLoop(self.customPath())
          try:
            devs = self._setupDevices(loop)
            return self._verifyImage(devs + '1')
          finally:
            self._cleanupDevices(loop)
        finally:
          self._cleanupLoop(loop)
      except:
        return False

  def _createSparseFile(self, path, len):
    """Create a sparse file.

    Create a sparse file with a given length, say for use as a disk
    image.

    It is the caller's responsibility to ensure that the passed in
    path doesn't exist, or can be overwritten.

    Args:
      path: Path to the file to be created.
      len: Length of the sparse file in bytes.
    """
    dir = os.path.dirname(path)
    if not os.path.exists(dir):
      os.makedirs(dir)
    open(path, 'w').truncate(len)

  def _runInTarget(self, command_args, *args, **kwargs):
    """Run a command in the install target.

    All extra positional and keyword arguments are passed on to
    captureCall.

    Args:
      command_args: The command and arguments to run within the
        target.
    """
    chroot_args = ['chroot', self.target]
    chroot_args.extend(command_args)
    return base.captureCall(chroot_args, *args, **kwargs)

  def _installFilesystem(self, path):
    """Create an ext3 filesystem in the device at path.

    path may be a file or a block device.

    Args:
      path: Path to the block device where a filesystem should be
        created.
    """
    base.captureCall(['mkfs', '-t', 'ext3', '-F', path])

  def _installSwap(self, path):
    """Create a swap area at path.

    path may be a file or a block device.

    Args:
      path: Path to the device where the swap area should be created
    """
    base.captureCall(['mkswap', path])

  @withoutInitScripts
  def _installPackages(self, *pkgs):
    """Install a series of packages in a chroot.

    Args:
      pkgs: The list of packages to install.
    """
    env = dict(os.environ)
    env['DEBIAN_FRONTEND'] = 'noninteractive'
    args = ['apt-get', '-y', 'install']
    args.extend(pkgs)
    self._runInTarget(args, env=env)

  @withoutInitScripts
  def _installReconfigure(self, pkg):
    """Reconfigure a package within a chroot.

    Args:
      pkg: The package to reconfigure.
    """
    self._runInTarget(['dpkg-reconfigure',
                       '-fnoninteractive',
                       '-pcritical',
                       pkg])

  def _installDebootstrap(self):
    """Debootstrap a basic Ubuntu install."""
    components = ','.join(self.getBaseConfig('components'))
    base.captureCall(['debootstrap',
                      '--keyring=%s' % self.getBaseConfig('keyring'),
                      '--arch=%s' % self.getBaseConfig('arch'),
                      '--components=%s' % components,
                      self.getBaseConfig('suite'),
                      self.target,
                      self.getBaseConfig('mirror')])

  def _installHosts(self):
    """Install the /etc/hosts file."""
    hosts = open(os.path.join(self.target, 'etc/hosts'), 'w')
    hosts.write("127.0.0.1 localhost\n"
                "\n"
                "# The following lines are desirable for IPv6 capable hosts\n"
                "::1 ip6-localhost ip6-loopback\n"
                "fe00::0 ip6-localnet\n"
                "ff00::0 ip6-mcastprefix\n"
                "ff02::1 ip6-allnodes\n"
                "ff02::2 ip6-allrouters\n"
                "ff02::3 ip6-allhosts\n")
    hosts.close()

  def _installSources(self):
    """Install the sources.list file."""
    sources = open(os.path.join(self.target, 'etc/apt/sources.list'), 'w')

    try:
      sources_conf = [
          self.getBaseConfig('mirror'),
          self.getBaseConfig('suite'),
          ' '.join(self.getBaseConfig('components'))]
      sources.write('deb %s %s %s\n' % tuple(sources_conf))
      sources.write('deb-src %s %s %s\n' % tuple(sources_conf))

      if self.getBaseConfig('enable_security'):
        sources_conf[0] = self.getBaseConfig('security_mirror')
        sources.write('deb %s %s-security %s\n' % tuple(sources_conf))
        sources.write('deb-src %s %s-security %s\n' % tuple(sources_conf))

      if self.getBaseConfig('enable_updates'):
        sources_conf[0] = self.getBaseConfig('updates_mirror')
        sources.write('deb %s %s-updates %s\n' % tuple(sources_conf))
        sources.write('deb-src %s %s-updates %s\n' % tuple(sources_conf))

      if self.getBaseConfig('enable_backports'):
        sources_conf[0] = self.getBaseConfig('backports_mirror')
        sources.write('deb %s %s-backports %s\n' % tuple(sources_conf))
        sources.write('deb-src %s %s-backports %s\n' % tuple(sources_conf))

      if self.getBaseConfig('enable_proposed'):
        sources_conf[0] = self.getBaseConfig('proposed_mirror')
        sources.write('deb %s %s-proposed %s\n' % tuple(sources_conf))
        sources.write('deb-src %s %s-proposed %s\n' % tuple(sources_conf))
    finally:
      sources.close()

  @withoutInitScripts
  def _installUpdates(self):
    """Take all pending updates."""
    env = dict(os.environ)
    env['DEBIAN_FRONTEND'] = 'noninteractive'
    self._runInTarget(['apt-get',
                       'update'],
                      env=env)
    self._runInTarget(['apt-get',
                       '-y',
                       'dist-upgrade'],
                      env=env)

  @withoutInitScripts
  def _installLocale(self):
    """Configure locale settings."""
    locale = open(os.path.join(self.target, 'etc/default/locale'), 'w')
    locale.write('LANG="en_US.UTF-8"\n')
    locale.close()

    locale_gen = open(os.path.join(self.target, 'etc/locale.gen'), 'w')
    locale_gen.write('en_US.UTF-8 UTF-8\n')
    locale_gen.close()

    self._installPackages('locales')

    self._runInTarget(['locale-gen'])
    self._installReconfigure('locales')

  @withoutInitScripts
  def _installTimezone(self):
    """Configure timezone settings."""
    timezone = open(os.path.join(self.target, 'etc/timezone'), 'w')
    timezone.write('America/Los_Angeles\n')
    timezone.close()

    self._installReconfigure('tzdata')

  def _installPartitions(self, img):
    """Partition a disk image.

    Right now, the disk is broken into a Linux partition, followed by
    a 1G swap partition. All remaining space past that 1G is allocated
    to the Linux partition.

    Args:
      img: Path to the image file to partition.
    """
    # TODO(ebroder): Allow for more arbitrary partitioning

    # This is slightly braindead math, but I don't really care about
    # the swap partition being /exactly/ 1G.
    disk_blocks = os.stat(img).st_size / (1024 ** 2)
    swap_blocks = 1024
    root_blocks = disk_blocks - swap_blocks

    base.captureCall(
        ['sfdisk', '-uM', img],
        stdin_str=',%d,L,*\n,,S\n;\n;\n' % root_blocks)

  def _setupLoop(self, img):
    """Setup a loop device for a disk image.

    Args:
      img: Path to the image file.

    Returns:
      The image exposed as a block device.
    """
    return base.captureCall(['losetup', '--show', '--find', img]).strip()

  def _cleanupLoop(self, blk):
    """Clean up a loop device for a disk image.

    Args:
      blk: The block device returned from _setupLoop
    """
    base.captureCall(['losetup', '-d', blk])

  def _setupDevices(self, blk):
    """Create device maps for partitions on a disk image.

    Args:
      blk: The block device

    Returns:
      The base path for the exposed partitions. Append an integer to
        get a particular partition. (i.e. return_value + '1')
    """
    base.captureCall(['kpartx', '-p', '', '-a', blk])
    return os.path.join('/dev/mapper', os.path.basename(blk))

  def _cleanupDevices(self, blk):
    """Cleanup the partition device maps.

    Args:
      blk: The block device
    """
    base.captureCall(['kpartx', '-p', '', '-d', blk])

  def _setupMapper(self, dev):
    """Create a device-mapper node mapping over a device.

    This creates a node named like a traditional hard drive, which
    will satisfy grub-install sufficiently to get it to install onto a
    disk image instead of an actual drive.

    Args:
      dev: The block device to create a mapping for. Usually a loop
        device.

    Returns:
      The new device mapper node
    """
    loop_stat = os.stat(dev)

    # The device-mapper takes sizes in units of 512-byte sectors,
    # which blockdev --getsz conveniently returns
    size = base.captureCall(['blockdev', '--getsz', dev]).strip()
    device = '%s:%s' % (os.major(loop_stat.st_rdev),
                        os.minor(loop_stat.st_rdev))
    # dm tables are "logical_start length linear device_to_map
    # device_start"
    table = '0 %s linear %s 0' % (size, device)

    # We don't really care what the node is actually called, just that
    # grub-install thinks it's a hard drive, so we'll try everything
    # it thinks is a hard drive
    for disk_type in ('sd', 'hd', 'vd'):
      for disk_id in string.ascii_lowercase:
        disk = disk_type + disk_id
        try:
          base.captureCall(['dmsetup', 'create', disk], stdin_str=table)
          return os.path.join('/dev/mapper', disk)
        except subprocess.CalledProcessError:
          continue
    else:
      raise errors.NoAvailableDevs(
        "Could not find an unused device-mapper name for '%s'" % dev)

  def _cleanupMapper(self, mapper_dev):
    """Cleanup a device-mapper node.

    Args:
      mapper_dev: The device-mapper node to cleanup.
    """
    base.captureCall(['dmsetup', 'remove', os.path.basename(mapper_dev)])

  def _copyFilesystem(self, src, dst):
    """Copy a filesystem.

    This copies all files in src into dst. Both src and dst should
    exist and be directories.

    All files will be copied, all properties preserved, etc.

    Args:
      src: Source of the copy.
      dst: Destination of the copy.
    """
    # I've said it before, I'll say it again. I /hate/ that rsync
    # changes its behavior based on a trailing slash.
    if not src.endswith('/'):
      src += '/'
    if not dst.endswith('/'):
      dst += '/'

    base.captureCall(['rsync', '--archive', src, dst])

  def _installFstab(self, filesystems):
    """Write an fstab into the target filesystem.

    The fstab is written using filesystem UUIDs, so block devices
    should be accessible to the installer, and not necessarily the
    path on which they will be exposed to the guest.

    Args:
      filesystems: A dict mapping paths in the target filesystem to
        block devices. "swap" is a special key indicating swap.

    Raises:
      debmarshal.errors.NotFound if any of the block devices in
        filesystems don't exist.
    """
    for block in filesystems.values():
      if not os.path.exists(block):
        raise errors.NotFound(
            "Block device '%s' does not exist.")

    fstab = open(os.path.join(self.target, 'etc/fstab'), 'w')
    fstab.write(
        '# /etc/fstab: static file system information.\n'
        '#\n'
        '# <file system>                                        '
        '<mount point> <type>  <options>       <dump>  <pass>\n')
    fs_tmpl = '%-54s %-13s %-7s %-15s %d       %d\n'

    fstab.write(fs_tmpl % ('proc', '/proc', 'proc', 'defaults', 0, 0))

    for mount, block in filesystems.iteritems():
      uuid = base.captureCall(['blkid', '-o', 'value', '-s', 'UUID', block])

      if mount == 'swap':
        fs_file = 'none'
        fs_type = 'swap'
        fs_passno = 0
      else:
        fs_file = mount
        fs_type = 'ext3'
        if mount == '/':
          fs_passno = 1
        else:
          fs_passno = 2

      fstab.write(fs_tmpl % (
          '/dev/disk/by-uuid/%s' % uuid.strip(),
          fs_file,
          fs_type,
          'defaults',
          0,
          fs_passno))

    fstab.close()

  def _installNetwork(self):
    """Configure networking."""
    hostname = open(os.path.join(self.target, 'etc/hostname'), 'w')
    hostname.write(self.getCustomConfig('hostname'))
    hostname.close()

    hosts = open(os.path.join(self.target, 'etc/hosts'), 'a')
    hosts.write('\n127.0.1.1 %(hostname)s.%(domain)s %(hostname)s\n' %
                {'hostname': self.getCustomConfig('hostname'),
                 'domain': self.getCustomConfig('domain')})
    hosts.close()

    interfaces = open(os.path.join(self.target, 'etc/network/interfaces'), 'w')
    interfaces.write(
        '# This file describes the network interfaces available on your\n'
        '# system and how to activate them. For more information, see\n'
        '# interfaces(5).\n'
        '\n'
        '# The loopback network interface\n'
        'auto lo\n'
        'iface lo inet loopback\n'
        '\n'
        '# The primary network interface\n'
        'auto eth0\n')
    if self.getCustomConfig('dhcp'):
      interfaces.write('iface eth0 inet dhcp\n')
    else:
      ip = self.getCustomConfig('ip')
      netmask = self.getCustomConfig('netmask')
      gateway = self.getCustomConfig('gateway')
      dns = self.getCustomConfig('dns')
      domain = self.getCustomConfig('domain')

      interfaces.write('iface eth0 inet static\n')
      interfaces.write('\taddress %s\n' % ip)
      interfaces.write('\tnetmask %s\n' % netmask)
      interfaces.write('\tgateway %s\n' % gateway)
      interfaces.write('\tdns-nameservers %s\n' % ' '.join(dns))
      interfaces.write('\tdns-search %s\n' % domain)

    interfaces.close()

  def _installKernelConfig(self):
    """Configure kernel images."""
    kernel_img = open(os.path.join(self.target, 'etc/kernel-img.conf'), 'w')
    kernel_img.write(
        "# Kernel image management overrides\n"
        "# See kernel-img.conf(5) for details\n"
        "do_symlinks = yes\n"
        "relative_links = yes\n"
        "do_bootloader = no\n"
        "do_bootfloppy = no\n"
        "do_initrd = yes\n"
        "link_in_boot = no\n")
    kernel_img.close()

  def _installBootloader(self, disk, root):
    """Install the GRUB bootloader onto a disk's MBR.

    Args:
      disk: The block device for the disk, as seen by the host.
      root: The block device for the root partition, as seen by the
        host.
    """
    # First we need to write out a fake device.map
    os.makedirs(os.path.join(self.target, 'boot/grub'))
    device_map = open(os.path.join(self.target, 'boot/grub/device.map'), 'w')

    device_map.write('(hd0) %s\n' % disk)
    device_map.close()

    base.captureCall(['grub-install',
                      '--root-directory=%s' % self.target,
                      disk])

    # Run update-grub once to create the menu.lst
    self._runInTarget(['bash', 'update-grub', '-y'])
    uuid = base.captureCall(
        ['blkid', '-o', 'value', '-s', 'UUID', root]).strip()
    self._runInTarget(['sed',
                       '-r', '-i',
                       '-e',
                       r's/^(# kopt=.*root=)[^ ]*/\1UUID=%s noapic/' % uuid,
                       '-e',
                       r's/^(# defoptions=).*$/\1/',
                       '/boot/grub/menu.lst'])

    # Run update-grub one more time to take the new defaults
    self._runInTarget(['bash', 'update-grub', '-y'])

  def _installExtraPackages(self):
    """Install and remove packages as configured.

    Part of the custom_config for Ubuntu images includes adding and
    removing certain packages. We do that here.
    """
    self._installPackages(*self.getCustomConfig('add_pkg'))
    self._installPackages(*('%s-' % pkg for pkg in
                            self.getCustomConfig('rm_pkg')))

  def _installSSHKey(self):
    """Install an ssh key for logins as root, if one is set."""
    if self.getCustomConfig('ssh_key'):
      os.makedirs(os.path.join(self.target, 'root/.ssh'))
      authorized_keys = open(os.path.join(self.target,
                                          'root/.ssh/authorized_keys'),
                             'w')
      authorized_keys.write(self.getCustomConfig('ssh_key') + '\n')

      authorized_keys.close()

  def createBase(self):
    """Create a valid base image.

    This method is responsible for creating a base image at
    self.basePath().

    No arguments are taken and no value is returned, because the
    location of the resulting base image is already known.
    """
    if self.verifyBase():
      return

    if os.path.exists(self.basePath()):
      os.remove(self.basePath())

    self._createSparseFile(self.basePath(), 1024 ** 3)
    try:
      self._installFilesystem(self.basePath())
      self.target = self._mountImage(self.basePath())

      try:
        self._installDebootstrap()
        self._installHosts()
        self._installSources()
        self._installUpdates()
        self._installLocale()
        self._installTimezone()
      finally:
        self._umountImage(self.target)
    except:
      os.remove(self.basePath())
      raise

  def createCustom(self):
    """Create a valid customized image.

    This method will create a customized disk image at
    self.customPath()

    No arguments are taken, and no value is returned.
    """
    if self.verifyCustom():
      return

    self.createBase()

    if os.path.exists(self.customPath()):
      os.remove(self.customPath())

    size = 10 * (1024 ** 3)
    self._createSparseFile(self.customPath(), size)
    try:
      self._installPartitions(self.customPath())
      loop = self._setupLoop(self.customPath())
      try:
        fake_disk = self._setupMapper(loop)
        try:
          devs = self._setupDevices(fake_disk)

          try:
            root = devs + '1'
            swap = devs + '2'
            self._installFilesystem(root)
            self._installSwap(swap)

            self.target = self._mountImage(root)
            try:
              base = self._mountImage(self.basePath())

              try:
                self._copyFilesystem(base, self.target)
              finally:
                self._umountImage(base)

              self._installFstab({'/': root, 'swap': swap})
              self._installNetwork()
              self._installKernelConfig()
              self._installPackages('grub')
              self._installPackages(self.getCustomConfig('kernel'))
              self._installBootloader(fake_disk, root)
              self._installExtraPackages()
              self._installSSHKey()
            finally:
              self._umountImage(self.target)
          finally:
            self._cleanupDevices(fake_disk)
        finally:
          self._cleanupMapper(fake_disk)
      finally:
        self._cleanupLoop(loop)
    except:
      os.remove(self.customPath())
      raise
