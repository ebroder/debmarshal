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
"""Create an Ubuntu image as an unprivileged user."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import fcntl
import os
import traceback
import urllib

import yaml


def genCommandLine(preseed):
  """Given a preseed file, generate a list of command line args.

  If the preseed file has some number of blocks starting with "###
  BEGIN COMMAND LINE ARGS" and ending with "### END COMMAND LINE
  ARGS", those Debconf options will be extracted and reformatted as
  part of the kernel command line.

  This function is not your mother; if your preseed file forgets the
  closing block, we won't tell you, and the behavior of the function
  is not well-defined.

  It's also your problem to be sure that none of the options to be
  passed in on the command line contain spaces, because the kernel
  isn't clever enough to deal with them.

  Args:
    preseed: Path to a Debconf preseed file.

  Returns:
    A string containing the arguments to pass on the kernel command
      line.
  """
  args = {}
  capturing_args = False
  for line in open(preseed):
    if line == '### BEGIN COMMAND LINE ARGS\n':
      capturing_args = True
    elif line == '### END COMMAND LINE ARGS\n':
      capturing_args = False

    if capturing_args and not line.lstrip().startswith('#'):
      opt, _, value = line.split()[1:5]
      args[opt] = value

  return ' '.join('%s=%s' % (k, v) for k, v in args.iteritems())


def loadKernel(suite, arch):
  """Make sure the kernel and initrd are available.

  This function downloads the kernel and initrd for the requested
  suite and architecture into
  ~/.cache/debmarshal/dists/ubuntu/<suite>.

  Args:
    suite: Which suite's kernel and initrd to download
    arch: What architecture to download.
  """
  # TODO(ebroder): Don't hardcode mirrors!
  base_url = (
    'http://us.archive.ubuntu.com/ubuntu/dists/' +
    suite +
    '/main/installer-%s/current/images/netboot/ubuntu-installer/%s/' % (
      arch, arch))
  base_cache = os.path.expanduser(os.path.join(
      '~/.cache/debmarshal/dists/ubuntu', suite))

  if not os.path.exists(base_cache):
    os.makedirs(base_cache)

  kernel_cache = os.path.join(base_cache, 'linux')

  kernel_lock = open(kernel_cache + '.lock', 'w')
  fcntl.lockf(kernel_lock, fcntl.LOCK_EX)
  if not os.path.exists(kernel_cache):
    try:
      urllib.urlretrieve(base_url + 'linux', kernel_cache)
    except:
      os.unlink(kernel_cache)
      raise
  del kernel_lock

  initrd_cache = os.path.join(base_cache, 'initrd.gz')

  initrd_lock = open(initrd_cache + '.lock', 'w')
  fcntl.lockf(initrd_lock, fcntl.LOCK_EX)
  if not os.path.exists(initrd_cache):
    try:
      urllib.urlretrieve(base_url + 'initrd.gz', initrd_cache)
    except:
      os.unlink(initrd_cache)
      raise
  del initrd_lock

  return (kernel_cache, initrd_cache)


def doInstall(test, vm, web_port, results_queue):
  """Start and monitor an unattended Ubuntu install.

  This function will start an unattended Ubuntu install, running in a
  VM, as part of a debmarshal test. It will also monitor that install
  to completion.

  This is intended to be run as a separate thread of execution, so
  that many installs can run in parallel.

  Its success or failure is reported back to the spawning process
  through the results_queue.

  Args:
    test: A path to a debmarshal test
    vm: The hostname of the vm within the test to install
    web_port: The port the test is being served over. The spawning
      process should be serving the directory containing the
      debmarshal test over HTTP.
    results_queue: A Queue.Queue object that doInstall will store its
      success or failure into that
  """
  try:
    config = yaml.safe_load(open(os.path.join(test, 'config.yml')))

    vm_config = config['vms'][vm]

    dist_name = vm_config['distribution']
    arch = vm_config.get('arch', 'x86_64')
    deb_arch = arch if arch != 'x86_64' else 'amd64'

    dist_opts = vm_config.get('dist_opts', {})
    suite = dist_opts.get('suite', 'jaunty')

    kernel, initrd = loadKernel(suite, deb_arch)

    preseed_path = os.path.join(test, '%s.preseed' % vm)
  except:
    results_queue.put((test, vm, False, traceback.format_exc()))
