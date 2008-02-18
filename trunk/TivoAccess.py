# Copyright (c) 2008, Brandon Long
# -*- coding: utf-8 -*-
#
# Library to remotely access Tivo DVRs.
#

import os
import urllib2
import Cookie
import BeautifulSoup
import html_unescape


try:
  import avahi_find_hosts
  has_avahi = 1
except ImportError:
  has_avahi = 0


class PlayListEntry:
  def __init__(self):
    self.title = ''
    self.episode = ''
    self.desc = ''
    self.date = 0
    self.size = ''
    self.channel = ''
    self.station = ''
    self.copyprotected = False
    self.url = ''
    self.details_url = ''
    self.inprogress = False

  def __str__(self):
    return ':'.join([self.title, self.desc, str(self.date), str(self.size), self.channel, self.url])


class TivoFetcher:
  def __init__(self, tivo_host, media_key):
    self.tivo_host = tivo_host
    self.media_key = media_key

    # The Tivo uses Digest Auth, with username 'TiVo DVR' and password as the
    # media access key.  Setup a urllib opener to have that auth information
    # for both http and https.
    authinfo = urllib2.HTTPDigestAuthHandler()
    authinfo.add_password('TiVo DVR', 'http://%s/' % (tivo_host), 'tivo', 
        media_key)
    authinfo.add_password('TiVo DVR', 'https://%s/' % (tivo_host), 'tivo',
        media_key)
    self.opener = urllib2.build_opener(authinfo)

    # The TiVo requires some other cookies for downloading videos.  Those
    # cookies are set when accessing the index, and stored here by
    # ExtractCookies to be used when downloading.
    self.cookies = Cookie.SimpleCookie()

  def Download(self, entry, destfn):
    # Use curl, since wget and urllib both generate bad data (one webpage
    # points to a bug in wget's chunked encoding handling)
    if not entry.url:
      print "Unable to download %s, no url" % (entry.title)
      return

    cookie_str = []
    for morsel in self.cookies.values():
      cookie_str.append("%s=%s" % (morsel.key, morsel.value))

    args = []
    args.append('curl')
    args.append('--silent')
    args.append('--cookie')
    args.append(';'.join(cookie_str))
    args.append('--digest')
    args.append('-u')
    args.append('tivo:%s' % self.media_key)
    args.append('--output')
    args.append('%s.dl' % destfn)
    args.append(entry.url)

    r = os.spawnvp(os.P_WAIT, 'curl', args)
    if r == 0:
      file_size = os.path.getsize('%s.dl' % destfn)
      # Check the size, it should be at least 60% of the size, and pretty big
      # 60% seems small, but I've seen Robot Chicken episodes as small as 66%
      # Actually, I've now seen episodes in the 35% range... but I don't know
      # if I want to make this that lenient.
      if (file_size < 100*1024*1024) or (file_size < 0.6 * int(entry.size)):
        print '%s file size too small: %d < %d' % (destfn, file_size,
            int(entry.size))
        return
      os.rename('%s.dl' % destfn, destfn)
    else:
      print '%s returned %d' % (' '.join(args), r)
    return

    # The urllib downloader, which generates a broken file.  I haven't
    # debugged this yet.
    headers = {}
    headers['Cookie'] = '; '.join(cookie_str)
    req = urllib2.Request(entry.url, headers=headers)
    f = self.opener.open(req)
    fpo = open(destfn, 'w')
    while 1:
      buf = f.read(65536)
      if not buf: break
      fpo.write(buf)

  def ExtractCookies(self, headers):
    if headers.has_key("set-cookie"):
      for value in headers.getheaders("set-cookie"):
        self.cookies.load(value)

  def FetchPlayList(self):
    # /TiVoConnect?Command=QueryContainer&Container=%2FNowPlaying&Recurse=Yes&AnchorOffset=0
    offset = 0
    totalcount = 0
    results = []
    while 1:
      url = "https://%s/TiVoConnect?Command=QueryContainer&Container=%%2FNowPlaying&Recurse=Yes&AnchorOffset=%d" % (self.tivo_host, offset)
      f = self.opener.open(url)
      self.ExtractCookies(f.headers)
      soup = BeautifulSoup.BeautifulStoneSoup(f.read())
      if totalcount == 0:
        totalcount = int(soup.tivocontainer.details.totalitems.string)
      for item in soup.tivocontainer.findAll('item'):
        entry = PlayListEntry()
        entry.title = html_unescape.unescape(item.details.title.string)
        if item.details.episodetitle:
          entry.episode = html_unescape.unescape(item.details.episodetitle.string)
        if item.details.description:
          entry.desc = html_unescape.unescape(item.details.description.string).replace('Copyright Tribune Media Services, Inc.', '').strip()
        entry.date = int(item.details.capturedate.string, 0)
        entry.size = item.details.sourcesize.string
        if item.details.sourcechannel:
          entry.channel = item.details.sourcechannel.string
          entry.station = item.details.sourcestation.string
        if item.details.inprogress:
          entry.inprogress = True
        entry.url = html_unescape.unescape(item.links.content.url.string)
        # urllib2's http auth support doesn't like :80
        entry.url = entry.url.replace(':80/', '/')
        if item.details.copyprotected:
          entry.copyprotected = True
        entry.details_url = html_unescape.unescape(item.links.tivovideodetails.url.string)
        results.append(entry)
      if len(results) < totalcount and offset < len(results):
        offset = len(results) + 1
      else:
        break

    return results


# What should we return if we don't have a mdns client?  Should this return an
# exception instead?
def FindTivos():
  if not has_avahi: return []
  return avahi_find_hosts.ReturnHosts('tivo_videos')


# Load the Tivo Media Access Key from the ~/.tivodecode_mak file
def LoadMak():
  return open(os.path.expanduser('~/.tivodecode_mak')).readline().strip()

