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

This module provides the primary command-line interface to the
debmarshal testing framework.

It handles preparation of VM disk images, as well as actually
executing the test.
"""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import optparse
import os
import Queue
import subprocess
import sys
import threading
import time

import yaml

from debmarshal.distros import base
from debmarshal import privops


USAGE = """Usage: debmarshal prepare [--options] [<test1> [<test2> ...]]"""


def usage():
  """Print out usage information, then error out."""
  print USAGE

  sys.exit(1)


def parsePrepareArgs(argv):
  """Parse command line options for the prepare subcommand.

  Args:
    argv: A list of all command line arguments after the subcommand.

  Returns:
    A 2-tuple of (options, arguments), where options is an object
      containing all options.
  """
  parser = optparse.OptionParser()
  # We don't actually have any options to parse yet, but they'll go
  # here if we ever do.

  return parser.parse_args(argv)


def prepareSummary(results_queue, start_time, stream=sys.stdout):
  """Given a queue of results from installations, print out a summary.

  This prints out a unittest-style summary of the installs that
  were logged in the passed-in results queue.

  It's the caller's responsibility to make sure that no other threads
  are reading from or writing to the results_queue while this function
  is running.

  Args:
    results_queue: A Queue.Queue containing the results of a series of
      VM installations. Each element in the queue should be of the
      form (test, vm_name, passed, error), where error is None if
      there was no error.
    start_time: Time in seconds since the epoch when the test suite
      started.
    stream: The stream to print the results to.

  Returns:
    The exit code for the preparation program - 1 if there were
      failures; 0 if there were none.
  """
  result_count = 0
  fail_count = 0
  while not results_queue.empty():
    result = results_queue.get()
    result_count += 1

    stream.write('Prepared %s ...' % result[1])
    if result[2]:
      stream.write('OK')
      if result[3] == 'cached':
        stream.write(' (cached)')
      stream.write('\n')
    else:
      fail_count += 1
      stream.write('F\n')

      stream.write(result[3])
      stream.write('\n')

  stream.write('\n')
  stream.write('%d VM%s built for %s in %.2f seconds\n' % (
      result_count,
      's' if result_count != 1 else '',
      result[0],
      time.time() - start_time))

  if fail_count:
    stream.write('(%d failed)\n' % fail_count)

  return int(bool(fail_count))


def prepareTest(test):
  """Prepare the disk image for a single test.

  Args:
    Path to a debmarshal test.
  """
  start = time.time()

  # First, load the configuration
  config = yaml.safe_load(open(os.path.join(test, 'config.yml')))

  # Next, network configuration. Configure the network as it will be
  # for the test run.
  vms = config['vms'].keys()
  net_name, net_gate, net_mask, net_vms = privops.call('createNetwork',
                                                       vms)

  try:
    # Then, spawn the web server for serving the test configuration.
    httpd = subprocess.Popen(['python', '-m', 'debmarshal.web', test],
                             stdout=subprocess.PIPE)
    web_port = httpd.stdout.read()

    try:
      results_queue = Queue.Queue()
      threads = []

      # For each VM that needs to be installed, create a thread to run
      # the installer
      for vm in vms:
        dist = base.findDistribution(config['vms'][vm]['distribution'])

        threads.append(threading.Thread(
            target=dist,
            args=(test,
                  vm,
                  net_name,
                  net_gate,
                  net_vms[vm][1],
                  web_port,
                  results_queue)))

      # Ready, set, go!
      for t in threads:
        t.start()

      # Wait until all of the threads have completed execution
      for t in threads:
        t.join()

      return prepareSummary(results_queue, start)
    finally:
      httpd.terminate()
  finally:
    privops.call('destroyNetwork', net_name)


def doPrepare(argv):
  """Prepare disk images for a series of tests.

  If no tests are specified, the current directory is assumed.

  Args:
    Command line arguments after the subcommand.

  Returns:
    The exit code for this subcommand.
  """
  opts, args = parsePrepareArgs(argv)

  if not args:
    args = [os.getcwd()]

  for test in args:
    prepareTest(test)


def _main(argv):
  """The main test runner. Dispatcher to subcommands.

  Args:
    All command line arguments.

  Returns:
    The exit code for the program.
  """
  if len(argv) == 0:
    usage()

  if argv[0] == 'prepare':
    return doPrepare(argv[1:])
  else:
    usage()


def main():
  """Run the main function with arguments from the command line."""
  sys.exit(_main(sys.argv[1:]))


if __name__ == '__main__':
  main()
