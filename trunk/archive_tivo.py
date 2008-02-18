#!/usr/bin/python
# 
# archive_tivo is a quick example of a program to selectively copy some 
# video's off your tivo

import sys
import os
import time
import TivoAccess
import progrun


DOWNLOAD = os.path.expanduser('~/Downloads')


def EntryFilename(entry):
  if entry.episode:
    fn = '%s - %s.tivo' % (entry.title, entry.episode)
  else:
    fn = '%s.tivo' % (entry.title)
  fn = fn.replace("'", '')
  fn = fn.replace(":", ' -')
  fn = fn.replace("/", ' - ')
  return os.path.join(DOWNLOAD, fn)


def main(argv):
  try:
    progrun.do_lock('/tmp/archive_tivo.lock')
  except progrun.LockFailed:
    return

  media_key = TivoAccess.LoadMak()
  hosts = TivoAccess.FindTivos()
  for host in hosts:
    tf = TivoAccess.TivoFetcher(host, media_key)
    entries = tf.FetchPlayList()
    matching = []
    for entry in entries:
      if entry.inprogress: continue
      for dl in ['South Park', 'Robot Chicken', 'Venture', 'NHL']:
        if entry.title.find(dl) != -1:
          if os.path.exists(EntryFilename(entry)): continue
          matching.append(entry)

    if len(matching):
      print "Tivo %s has %d shows, %d to download" % (host, len(entries),
          len(matching))
      for entry in matching:
        print "Downloading %s" % EntryFilename(entry)
        tf.Download(entry, EntryFilename(entry))
        # wait 15s between downloads to let the tivo recover
        time.sleep(15)


if __name__ == "__main__":
  main(sys.argv)
