#!/usr/bin/python2.4
#
# Copyright 2006 Google Inc. All Rights Reserved.

"""Script to index package files in the pool hierarchy

The index_pool.py script is a repository-administrator command that
traverses through the pool/ hierarchy and indexes all package files it
finds there.  The script skips over files that have already been
indexed, so the indexing operation is practically idempotent.
"""

__author__ = 'cklin@google.com (Chuan-Kai Lin)'

import logging as lg
import os
import sys
import bsddb_utils as bu
import deb_utils as du
import logging_utils as lu
import os_utils as ou
import package_utils as pu
import release_utils as ru
import setting_utils as su


_new_package = False


def IndexPool((src_names, pkg_names), dbs):
  """Index the specified source and binary packages

  This function accepts lists of source and binary package pathnames
  as input and indexes those package files into the database.  This
  step is necessary for debmarshal to consider a package for release.
  Note that the package files should be at their final location; once
  indexed, they should never again be moved.
  """

  def IndexSource(name):
    """Index a source package (pool_pkg, src_info)
    """

    global _new_package

    src = os.path.split(name)[1]
    if src in pool_pkg:
      file_size = str(os.stat(name).st_size)
      if pool_pkg[src] != file_size:
        lg.warning('File ' + name + ' does not match indexed data')
      return

    lg.info('Indexing ' + name)
    pool_pkg[src] = str(os.stat(name).st_size)
    lines = ou.RunWithFileInput(pu.StripSignature, name)
    attr_dict = pu.ParseAttributes(lines)
    nv = pu.GetSourceID(attr_dict)
    src_info[nv] = du.BuildSrcInfoText(name, attr_dict)
    _new_package = True

  def IndexBinary(name):
    """Index a binary package (pool_pkg, pkg_info, pkg_deps, file_pkg)
    """

    global _new_package

    pkg = os.path.split(name)[1]
    if pkg in pool_pkg:
      file_size = str(os.stat(name).st_size)
      if pool_pkg[pkg] != file_size:
        lg.warning('File ' + name + ' does not match indexed data')
      return

    lg.info('Indexing ' + name)
    pool_pkg[pkg] = str(os.stat(name).st_size)

    try:
      contents, attr_dict = du.ParseDebInfo(os.path.abspath(name))
    except IOError:
      lg.warning('File ' + name + ' threw an IOError while parsing.  ' +
                 'Discarding bad .deb')
      return

    nva = pu.GetPackageID(attr_dict)
    pkg_info[nva] = du.BuildDebInfoText(name, attr_dict)
    pkg_deps[nva] = du.BuildDependencyString(name, attr_dict)
    _new_package = True

    # We do not enter the debian-installer packages into file_pkg
    # because these packages are never installed on a normal system.

    if not name.endswith('.udeb'):
      for f in contents:
        bu.AppendEntry(file_pkg, f, nva)

  pkg_info = dbs['pkg_info']
  src_info = dbs['src_info']
  pkg_deps = dbs['pkg_deps']
  file_pkg = dbs['file_pkg']
  pool_pkg = dbs['pool_pkg']

  for name in src_names:
    IndexSource(name)
  for name in pkg_names:
    IndexBinary(name)
  return ru.SelectLatestPackages(pkg_info)


def _TraversePool():
  """Compile lists of package files in the pool hierarchy
  """

  def DoTraverse(_arg, dir, names):
    for name in names:
      if name.endswith('.dsc'):
        src_names.append(os.path.join(dir, name))
      elif name.endswith('.deb') or name.endswith('.udeb'):
        pkg_names.append(os.path.join(dir, name))

  src_names = []
  pkg_names = []
  os.path.walk('pool', DoTraverse, None)
  return src_names, pkg_names


def main(repo_dir):
  global _new_package

  current_cwd = os.getcwd()
  lu.SetLogConsole()
  try:
    os.chdir(repo_dir)
    if su.GetSetting(None, 'Mode') != 'tracking':
      lg.error('Repository is not in tracking mode')
      sys.exit()
    try:
      names = _TraversePool()
      packages = bu.RunWithDB(None, IndexPool, names)
      if _new_package:
        ru.GenerateReleaseList('snapshot', packages)
    except KeyboardInterrupt:
      lg.info('Received keyboard interrupt, terminating...')
  finally:
    os.chdir(current_cwd)


if __name__ == '__main__':
  if len(sys.argv) == 2:
    main(sys.argv[1])
  else:
    main(os.getcwd())
