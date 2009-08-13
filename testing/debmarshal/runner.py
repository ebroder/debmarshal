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
"""The debmarshal test runner.

This module provides the main debmarshal test runner. The test runner
first creates debmarshal network and a series of customized guest
images.

The runner then boots all of the VMs using memory-backed copy-on-write
snapshots of the disk images, plus an additional VM to isolate test
execution from the host.

The test execution script is transfered to the tester VM and executed;
its exit code informs the result of the test.
"""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import optparse
import os
import shutil
import sys
import tempfile
import traceback

import dbus
import yaml

from debmarshal.distros import base
from debmarshal import privops


def _parseOptions(argv):
  """Parse command line options.

  Args:
    A list of options from a command line.

  Returns:
    A 2-tuple of (options, arguments) where options is an object
      containing all options
  """
  parser = optparse.OptionParser()
  # We don't take any options yet, or they'd go here.

  return parser.parse_args(argv)


def _loadTest(test):
  """Load and validate the configuration for a test.

  Returns:
    A dict containing the test configuration.

  Raises:
    AssertionError if the test is not correctly configured.
  """
  config_path = os.path.join(test, 'config.yml')
  assert os.path.exists(config_path)
  assert os.path.exists(os.path.join(test, 'script'))

  config = yaml.safe_load(open(config_path))

  assert len(config['vms']) > 0

  return config


def _runTest(test):
  """Actually execute a test.

  Args:
    Directory where the test is stored.

  Returns:
    True if the test passes; False otherwise.
  """
  config = _loadTest(test)

  hostnames = [vm['hostname'] for vm in config['vms'].values()]
  net_config = privops.call('createNetwork', hostnames)

  try:
    images = {}
    domains = {}

    try:
      for vm_name, vm in config['vms'].items():
        custom_config = vm['custom_config']
        custom_config['hostname'] = vm['hostname']
        custom_config['domain'] = config['domain']

        privops.callWait('generateImage',
                         vm['distribution'],
                         vm['base_config'],
                         custom_config)

        custom_path = base.findDistribution(vm['distribution'])(
          vm['base_config'], custom_config).customPath()

        fd, copy_path = tempfile.mkstemp()
        os.close(fd)
        base.captureCall(['cp', custom_path, copy_path])
        images[vm_name] = copy_path

      try:
        for vm, image in images.items():
          domains[vm] = privops.createDomain(
            # memory
            config['vms'][vm].memory,
            # disks
            [image],
            # network
            net_config[0],
            # mac
            net_config[3][config['vms'][vm]['hostname']][1],
            # hypervisor
            'kvm',
            # arch
            'x86_64')

      finally:
        for domain in domains.values():
          privops.call('destroyDomain', domain)

    finally:
      for image in images.items():
        os.unlink(image)

  finally:
    privops.call('destroyNetwork', net_config[0])


def _printSummary(run, failures, errors, stream=sys.stdout):
  """Print out a summary of the test run, similar to unittest.

  Args:
    run: The total number of tests run.
    failures: The number of tests that failed
    errors: The number of tests that threw exceptions.
    stream: Where to output the summary, if not stdout.
  """
  print >>stream, '-' * 70
  print >>stream, 'Ran %d test%s' % (run, 's' if run != 1 else '')

  if failures or errors:
    stream.write('FAILED (')

    if failures and errors:
      stream.write('failures=%d, errors=%d' % (failures, errors))
    elif failures:
      stream.write('failures=%d' % failures)
    else:
      stream.write('errors=%d' % errors)

    print >>stream, ')'
  else:
    print >>stream, 'OK'


def _main(argv):
  """The main test runner.

  Args:
    All command line arguments.

  Returns:
    The exit code for the program.
  """
  options, tests = _parseOptions(argv)

  if not tests:
    tests = [os.getcwd()]

  # TODO(ebroder): See if we can leverage infrastructure from the
  #   unittest module to do most of this
  failures = 0
  errors = 0
  for test in tests:
    test = os.path.abspath(test)

    print 'Running %s ... ' % test,
    try:
      if _runTest(test):
        print 'OK'
      else:
        print 'F'
        failures += 1
    except:
      print 'E'
      print traceback.print_exc()
      errors += 1

  _printSummary(len(tests), failures, errors)

  if failures or errors:
    return 1
  else:
    return 0


def main():
  """Run the main function with arguments from the command line."""
  sys.exit(_main(sys.argv[1:]))


if __name__ == '__main__':
  main()
