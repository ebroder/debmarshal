#!/usr/bin/python2.4
#
# Copyright 2006 Google Inc.
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


"""Logging and error reporting utility functions

The logging_utils module contains utility functions for logging and
error reporting.  The messages can go either to the standard error or
to an email message sent to a specified recipient.
"""

__author__ = 'cklin@google.com (Chuan-Kai Lin)'

import logging
import logging.handlers as handlers
import socket
import cStringIO
import email.MIMEText as mime
import smtplib


_hdlr = None
_sio = None


def _ResetLog(root):
  global _hdlr
  global _sio

  if _hdlr is not None:
    root.removeHandler(_hdlr)
    _hdlr = None
  _sio = None


def SetLogConsole():
  """Set logging output to standard error

  This function sets the logger to output to the console (standard
  error) in a slightly-customized message format.  Any program that
  produces logging output should call this function on startup.
  """

  global _hdlr

  root = logging.getLogger()
  _ResetLog(root)
  _hdlr = logging.StreamHandler()
  formatter = logging.Formatter('%(levelname)-8s %(message)s')
  _hdlr.setFormatter(formatter)
  root.setLevel(logging.INFO)
  root.addHandler(_hdlr)


def SetLogBuffer():
  """Set logging output to string IO for later use

  This function sets the logger to output to a cStringIO buffer for
  later use.  A program that wishes to send its logging output out in
  an email later using the MailLog() function should call this
  function on startup.
  """

  global _hdlr
  global _sio

  root = logging.getLogger()
  _ResetLog(root)
  _sio = cStringIO.StringIO()
  _hdlr = logging.StreamHandler(_sio)
  formatter = logging.Formatter('%(message)s')
  _hdlr.setFormatter(formatter)
  root.setLevel(logging.INFO)
  root.addHandler(_hdlr)


def MailLog(host, msg_from, msg_to, msg_subj):
  """Send stored log messages in an email

  This function constructs an email message with all log messages
  stored in the cStringIO buffer and sends the message to the
  specified recipient.  To use this function, call SetLogBuffer()
  before generating the log messages.
  """

  global _sio

  if _sio is None:
    return
  if host is None:
    host = 'localhost'

  contents = _sio.getvalue()
  msg = mime.MIMEText(contents)
  msg['Subject'] = msg_subj
  msg['From'] = msg_from
  msg['To'] = msg_to

  try:
    s = smtplib.SMTP()
    s.connect(host)
    s.sendmail(msg_from, [msg_to], msg.as_string())
    s.close()
  except socket.error, mesg:
    SetLogConsole()
    logging.error('Socket error to ' + host + ' ' + str(mesg))
  except smtplib.SMTPException, mesg:
    SetLogConsole()
    logging.error('SMTP error to ' + host + ' ' + str(mesg))
