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
"""A simple webserver for serving debmarshal configuration.

This script will choose a random port and serve all files from a
directory over HTTP on that port.

It's intended for serving preseed and configuration files for
debmarshal test suites to the guests for easy access.

The port selected is written to stdout for the spawning proess to find
it.

If there is an additional argument, that is used as the directory to
serve content from. Otherwise the current directory is used.
"""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import BaseHTTPServer
import os
import SimpleHTTPServer
import sys


def serve(serve_dir):
  """Spawn an HTTP server, and echo back the port it's listening on.

  If you're using debmarshal.web from Python, it may be easier to fork
  and call this function directly instead of exec'ing the
  debmarshal.web module."""
  os.chdir(serve_dir)

  # Serve on all interfaces, and have the kernel choose a port
  server_address = ('', 0)
  httpd = BaseHTTPServer.HTTPServer(server_address,
                                    SimpleHTTPServer.SimpleHTTPRequestHandler)

  print httpd.server_port

  # Close stdin, stdout, and stderr
  for i in xrange(3):
    try:
      os.close(i)
    except:
      pass

  os.open('/dev/null', os.O_RDWR)
  os.dup2(0, 1)
  os.dup2(0, 2)

  httpd.serve_forever()


def main():
  """A wrapper for running serve as a script."""
  if len(sys.argv) > 1:
    serve_dir = sys.argv[1]
  else:
    serve_dir = os.getcwd()

  serve(serve_dir)


if __name__ == '__main__':
  main()
