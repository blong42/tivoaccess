import fcntl
import os
import sys

class LockFailed(Exception):
  pass

def do_lock(filename):
  lockfp = open(filename,"wb")
  try:
      fcntl.lockf(lockfp.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)
  except IOError, reason:
      sys.stderr.write("Unable to lock %s: %s\n" % (filename, str(reason)))
      raise LockFailed, reason

  lockfp.write("%d" % os.getpid())
  lockfp.truncate()
  return lockfp
