#!/usr/bin/python2.4
#
# Copyright 2006 Google Inc. All Rights Reserved.

"""Script to process package uploads in the incoming queue

The enter_incoming.py script is a repository-administrator command
that processes the uploaded files in the incoming queue (the incoming
subdirectory in the repository).  Uploads that pass all checks are
installed in the pool and, if they have the highest version numbers,
included in the new snapshot release.
"""

__author__ = 'cklin@google.com (Chuan-Kai Lin)'

import logging as lg
import os
import shutil
import sys
import time
import bsddb_utils as bu
import crypto_utils as cu
import index_pool as ip
import logging_utils as lu
import os_utils as ou
import package_utils as pu
import release_utils as ru
import setting_utils as su


def _GetUploadedFiles(changes_dict):
  """Get the list of uploaded files from the .changes file

  This function returns a dictionary that maps each file in the upload
  to the hexadecimal string of its MD5 hash value.  The input is a
  parsed attribute string of the .changes file.
  """

  md5sum = {}
  for spec_string in changes_dict['Files']:
    spec = spec_string.split()
    md5sum[spec[4]] = spec[0]
  return md5sum


def _ProcessChangesFile(changes, repo_dir, lists, dbs):
  """Process a .changes file which represents an upload
  """

  src_names, pkg_names = lists
  incoming_dir = os.path.join(repo_dir, 'incoming')
  src_info = dbs['src_info']
  pool_pkg = dbs['pool_pkg']

  # Remove the .changes file from the incoming directory and check its
  # signature (raise EnvironmentError if not properly signed).

  ou.CopyDeleteFiles(incoming_dir, '.', [changes])
  cu.VerifySignature(changes)

  # Parse the .changes file into a Python dictionary.

  lines = ou.RunWithFileInput(pu.StripSignature, changes)
  changes_dict = pu.ParseAttributes(lines)
  md5_dict = _GetUploadedFiles(changes_dict)
  version = changes_dict['Version'][0]
  source_pkg = changes_dict['Source'][0]

  # Establish the status of the upload in relation to the repository.
  # Is the source package already in the repository?  Is the upstream
  # source already in the repository?  It this a native package?

  new_source = True
  new_upstream = True
  native = True

  if (source_pkg + '_' + version) in src_info:
    new_source = False
  if version.find('-') != -1:
    upstream_ver = '-'.join(version.split('-')[:-1])
    source_header = source_pkg + '_' + upstream_ver + '-'
    if bu.FindKeyStartingWith(source_header, src_info):
      new_upstream = False
    native = False

  # Now check the contents of the upload.  Does it have native source,
  # upstream source, or Debian diff?  Is any of the files being
  # uploaded already present in the pool?

  has_source = False
  has_diff = False
  has_tar = False
  has_orig_tar = False

  for name in md5_dict:
    if name in pool_pkg:
      lg.error('File ' + name + ' is already in the pool')
      raise EnvironmentError
    if name.endswith('.dsc'):
      has_source = True
    elif name.endswith('.orig.tar.gz'):
      has_orig_tar = True
    elif name.endswith('.orig.tar.bz2'):
      has_orig_tar = True
    elif name.endswith('.tar.gz'):
      has_tar = True
    elif name.endswith('.tar.bz2'):
      has_tar = True
    elif name.endswith('.diff.gz'):
      has_diff = True

  # Check if the contents of the upload matches with its status (in
  # accordance with the Debian Policy).  You can relax the rules by
  # modifying the checks, but make sure that the modified logic still
  # requires all binary packages to come with sources.

  if new_source:
    if not has_source:
      lg.error('New package upload must contain source .dsc')
      raise EnvironmentError
    if native:
      prefix = 'New native package upload must '
      if has_diff:
        lg.error(prefix + 'not contain .diff')
        raise EnvironmentError
      if has_orig_tar:
        lg.error(prefix + 'not contain upstream .orig.tar')
        raise EnvironmentError
      if not has_tar:
        lg.error(prefix + 'contain source .tar')
        raise EnvironmentError
    else:
      prefix = 'New non-native package upload must '
      if not has_diff:
        lg.error(prefix + 'contain .diff')
        raise EnvironmentError
      if new_upstream:
        if not has_orig_tar:
          lg.error('New upstream non-native package upload ' +
                   'must contain upstream .orig.tar')
          raise EnvironmentError
      else:
        if has_orig_tar:
          lg.error('New distribution non-native package upload ' +
                   'must not contain upstream .orig.tar')
          raise EnvironmentError
      if has_tar:
        lg.error(prefix + ' not contain source .tar')
        raise EnvironmentError

  # Move rest of the uploaded files from incoming to the current
  # (temp) directory and check their MD5 hash value (raise
  # EnvironmentError if the hash values disagree).

  ou.CopyDeleteFiles(incoming_dir, '.', md5_dict)
  cu.VerifyMD5Hash(md5_dict)

  # Move uploaded files (along with .changes) into the pool.

  pool_loc = pu.GetPathInPool(source_pkg)
  pool_dir = os.path.join(repo_dir, pool_loc)
  ou.CopyDeleteFiles('.', pool_dir, md5_dict)
  ou.CopyDeleteFiles('.', pool_dir, [changes])

  # Compile the list of source package files (src_names) and binary
  # package files (pkg_names) added to the repository by this upload.
  # There is no need to return these lists because they are passed in
  # by reference.

  for name in md5_dict:
    if name.endswith('.dsc'):
      src_names.append(os.path.join(pool_loc, name))
    elif name.endswith('.deb') or name.endswith('.udeb'):
      pkg_names.append(os.path.join(pool_loc, name))


def main(repo_dir):

  def DoProcessWithDB(_arg, dbs):
    """Incoming processing operations with Berkeley DB tables
    """

    def DoProcessInTempDir():
      """Incoming processing operations in a temporary directory
      """

      processed = False
      files = os.listdir(os.path.join(repo_dir, 'incoming'))
      for name in files:

        # Ignore all files that does not have the .changes extension
        # and all files whose mtime is less than 5 seconds ago (to
        # avoid upload race condition).

        if not name.endswith('.changes'):
          continue
        changes_pathname = os.path.join(repo_dir, 'incoming', name)
        if time.time()-os.path.getmtime(changes_pathname) <= 5:
          continue

        # Process an upload and map exceptions to error messages.

        processed = True
        lg.info('Start processing ' + name + ' upload...')
        try:
          _ProcessChangesFile(name, repo_dir, new_files, dbs)
          lg.info('Processing of ' + name + ' succeeded.')
        except EnvironmentError:
          lg.error('Failed to process ' + name)
        except ValueError:
          lg.error('Failed to process ' + name)
        except IOError:
          lg.error('Failed to process ' + name + ' due to I/O error.')
        except OSError:
          lg.error('Failed to process ' + name + ' due to OS error.')
        lg.info('---- End of upload processing ----')
      return processed

    return ou.RunInTempDir(DoProcessInTempDir)

  def DoSnapshot(_arg, dbs):
    return ru.SelectLatestPackages(dbs['pkg_info'])

  os.chdir(repo_dir)

  # Store all incoming processing logs in a buffer for inclusion in
  # the email if both the Mailto and the Mailhost attributes are set.

  lu.SetLogConsole()
  msg_from = su.GetSetting(None, 'Admin')
  msg_to = su.GetSetting(None, 'Mailto')
  host = su.GetSetting(None, 'Mailhost')
  if not (msg_from is None or msg_to is None):
    lu.SetLogBuffer()

  new_files = [], []
  db_list = ['src_info', 'pool_pkg']
  processed = bu.RunWithDB(db_list, DoProcessWithDB)

  # If the processed flag is set, at least one .changes file has been
  # processed (successfully or otherwise).  Index the files we just
  # copied into the pool (ignore files in the pool that did not go
  # through the incoming process), generate a new snapshot release,
  # and send the logs by mail.

  if processed:
    if new_files[0] or new_files[1]:
      bu.RunWithDB(None, ip.IndexPool, new_files)
      latest = bu.RunWithDB(['pkg_info'], DoSnapshot)
      ru.GenerateReleaseList('snapshot', latest)
    if not (msg_from is None or msg_to is None):
      subject = 'Incoming processing logs, ' + time.asctime()
      lu.MailLog(host, msg_from, msg_to, subject)


if __name__ == '__main__':
  if len(sys.argv) >= 2:
    main(os.path.abspath(sys.argv[1]))
  else:
    main(os.getcwd())
