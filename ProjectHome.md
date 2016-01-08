Series 2 & 3 tivo's can be remotely accessed via http.  Normally, this is done by the Tivo Desktop software.  This module allows you to list and download videos from your Tivo using python, allowing you to script access to your tivo videos.

Conceptually similar to Perl's Net::Tivo, though I didn't look at it very closely.

Currently depends on [BeautifulSoup](http://www.crummy.com/software/BeautifulSoup/) for easy handling of the XML response from the Tivo.

Also depends on [avahi](http://avahi.org/) for mdns browsing to find the Tivo's on your network.  You can specify your Tivo by IP address if you don't have avahi installed (running?).

For more information, see:
  * [tivodecode](http://tivodecode.sourceforge.net/) - For removing the Tivo video wrapper, leaving you with an mpeg2 file
  * [Net::Tivo](http://www.cpan.org/modules/by-module/Net/Net-TiVo-0.09.readme) - Perl module
  * [Galleon](http://galleon.tv/) - Java based Tivo HME desktop client and more

Note that access to the Tivo data and downloads are SLOW.  In order to protect the interactive performance of the Tivo, it heavily constrains the amount of resources the web interface can use.  This is on top of any limitations of the connection you have to your Tivo.