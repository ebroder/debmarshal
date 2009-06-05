#!/usr/bin/python
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

""" Quick and dirty way to generate some random file structure

Use maxbytes, maxfolders, maxdepth, maxsize, and minsize to come up with
some (loose) guidelines for how you want the files to come out. Each file
and folder is guaranteed to have a unique name. Files are filled from /dev/zero
using dd.

"""

__author__ = 'willn@google.com (Will Nowak)'

import random
import os
import subprocess

class RandomFiles:
  def __init__(self):
    self._maxbytes = 436870912000
    self._maxfolders = 500
    self._maxdepth=5
    self._maxsize=524288000
    self._minsize=1024

    self._createdfolders = 0
    self._createdbytes = 0
    self._createdfiles = 0
    self._namelength = 8
    self._namesused = []

  def mkfile(self, filename, bytes):
    """ Create a file with name filename and size bytes in bytes """
    cmd = '/bin/dd if=/dev/zero of=%s bs=%s count=1' % (filename, bytes)
    p = subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print cmd
    p.wait()
    print p.stderr.read()

  def mkdir(self, dir):
    """ Make a directory named dir """
    print 'Making dir %s' % (dir)
    os.mkdir(dir)

  def uniquename(self):
    """ Return a unique name, using the defined alphabet and keeping track of
    names generated.
    """
    alphabet = 'abcefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'
    alphabet += '._+--'
    newname = ''
    for i in range(self._namelength+1):
      char = random.randint(0, len(alphabet)-1)
      newname += alphabet[char]
    if newname in self._namesused:
      newname = self.uniquename()
    else:
      self._namesused.append(newname)
      return newname

  def createfile(self, wd):
    """ Create a file in working directory wd. Use random filesize and name,
    trying to be smart and stay within our maxsize """
    filesize = (random.randint(self._minsize, self._maxsize) / 3)
    filename = '%s/%s' % (wd, self.uniquename())
    newtotal = self._createdbytes + filesize
    if newtotal > self._maxbytes:
      filesize = 10
    self.mkfile(filename, filesize)
    self._createdbytes += filesize
    self._createdfiles += 1

  def createfiles(self, count, wd):
    """ Create count files in directory wd """
    for i in range(count+1):
      self.createfile(wd)

  def createfolder(self, wd):
    """ Create a folder with random files observing the maxdepth rule """
    depth = wd.count('/')
    foldername = self.uniquename()
    self.mkdir('%s/%s' % (wd, foldername))
    self._createdfolders += 1
    if depth < self._maxdepth:
      for i in range(random.randint(0,4)):
        self.createfolder(wd+'/'+foldername)
    self.createfiles(random.randint(0,10), wd)

  def createfolders(self, count, wd):
    """ Create count folders in directory wd using self.createfolder() """
    for i in range(count+1):
      self.createfolder(wd)

  def main(self, wd='.'):
    """ Main function, do all work from here. Create folders and files
    observing the limits set in __init__.
    """
    while self._createdbytes < self._maxbytes:
      self.createfiles(10, wd)
      self.createfolders(10, wd)
    print 'Made %s folders and %s files totalling %s bytes' % (
        self._createdfolders, self._createdfiles, self._createdbytes)

if __name__ == '__main__':
  rf = RandomFiles()
  rf.main()
