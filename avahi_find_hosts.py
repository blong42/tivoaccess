#!/usr/bin/python
# $Id$

# This file is part of avahi.
#
# avahi is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# avahi is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
# License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with avahi; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA.

"""
avahi-find-hosts is a command line program intended to be used to fetch
a list of machines on the local network that are advertising a particular
service.

It can return IP addresses, fully qualified domain names or, in the cases
where the service supports it, URLs.

Modified by blong to be callable
"""

__author__ = "John Morton"
__version__ = "$Revision$"
__date__ = "$Date$"
__copyright__ = "Copyright (c) 2007 John Morton"
__license__ = "LGPL"

import sys
import optparse
import re

import gobject
import dbus
import avahi
import avahi.ServiceTypeDatabase

# Automatically sets the default mainloop for dbus to a Glib provided one.
# Needed to get signals to work.
import dbus.glib

debug = False

# Maps simple protocol names to the DNS resource service type, and url scheme
# name, if building URLs for that service makes sense.
# In the absence of an explicit entry here, the the name will be mapped as
# service->_service._tcp, which works in most cases.

service_map = { "ftp":          dict(stype="_ftp._tcp",
                                     url_scheme='ftp'),
                "http":         dict(stype="_http._tcp",
                                     url_scheme='http'),
                "https":        dict(stype="_https._tcp",
                                     url_scheme='https'),
                "nfs":          dict(stype="_nfs._udp",
                                     url_scheme='nfs'),                
                "rsync":        dict(stype="_rsync._tcp",
                                     url_scheme='rsync'),
                "ssh":          dict(stype="_ssh._tcp",
                                     url_scheme='ssh'),
                "sftp":         dict(stype="_sftp_ssh._tcp",
                                     url_scheme='sftp'),
                "workstation":  dict(stype="_workstation._tcp",
                                     ),
                
                }

# An index for mapping the DNS service type directly to the URL scheme.
stype_map = {}
for s in service_map:
    if service_map[s].has_key('url_scheme'):
        stype_map[service_map[s]['stype']] = service_map[s]['url_scheme']
del s


parser = optparse.OptionParser(
    usage="%prog [options] <service>" )

parser.set_defaults(
    debug=False,
    use_host_names=True,
    output="hosts",
    domain="local",
    timeout=3000
    )
                    
parser.add_option("-t", "--timeout", dest="timeout", 
                  help="Timeout for service browsing.")
parser.add_option("-d", "--domain",  dest="domain",
                  help="Default domain for browsing")
parser.add_option("-H", "--hostnames", dest="use_host_names",
                  action="store_const", const=True,
                  help="Resolve to host names")
parser.add_option("-A", "--addresses", dest="use_host_names",
                  action="store_const", const=False,
                  help="Resolve to addresses")
parser.add_option("-u", "--output-urls", dest="output",
                  action="store_const", const="urls",
                  help="Output URLs")
parser.add_option("--debug", dest="debug", action="store_true", )


class Service(object):
    """A simple structure to store the date that Avahi will retrieve when
    resolving a service."""

    def __init__(self, interface, protocol, name, stype, domain,
                 host, aprotocol, address, port, txt, flags):
        self.interface = interface
        self.protocol = protocol
        self.name = name
        self.type = stype
        self.domain = domain
        self.host = host
        self.aprotocol = aprotocol
        self.address = address
        self.port = port
        self.txt = avahi.txt_array_to_string_array(txt)
        self.flags = flags
        
    def key(self):
        """Provides a tuple of attributes suitable for using as a
        lookup key."""
        return (self.interface, self.protocol,
                self.name, self.type, self.domain)
        

class AvahiServices(object):
    """A class to encapsulate the business of talking to the avahi-daemon over
    the D-bus."""
    
    def __init__(self, domain, loop):
        """Sets up the connection to avahi-daemon over D-bus."""
        
        # Connect to the system bus...
        self.bus = dbus.SystemBus()
        # Get a proxy to the object we want to talk to.
        avahi_proxy = self.bus.get_object(avahi.DBUS_NAME,
                                          avahi.DBUS_PATH_SERVER)
        # Set the interface we want to use; server in this case.
        self.server = dbus.Interface(avahi_proxy, 
                                     avahi.DBUS_INTERFACE_SERVER)
        
        self.version_string = self.server.GetVersionString()
        self.domain = domain
        self.loop = loop
        self.services = {}

    def browse_service_type(self, stype):
        """Sets up call back methods to browse for a specific service type"""
        # Ask the server for a path to the browser object for the
        # service we're interested in...
        browser_path = self.server.ServiceBrowserNew(avahi.IF_UNSPEC,
                                                     avahi.PROTO_UNSPEC,
                                                     stype, self.domain,
                                                     dbus.UInt32(0))
        # Get it's proxy object...
        browser_proxy = self.bus.get_object(avahi.DBUS_NAME, browser_path)
        # And set the interface we want to use        
        browser = dbus.Interface(browser_proxy,
                                 avahi.DBUS_INTERFACE_SERVICE_BROWSER)

        # Now connect the call backs to the relevant signals.
        browser.connect_to_signal('ItemNew', self.new_service)
        browser.connect_to_signal('ItemRemove', self.remove_service)
        browser.connect_to_signal('AllForNow', self.all_for_now)

    
    def new_service(self, interface, protocol, name, stype, domain, flags):
        """Callback method used to handle a new service has appearing, or
        a known one being retrieved from avahi-daemon's cache.

        Adds a Service object to our collection.  """
        
        service = Service(*self.server.ResolveService(
            interface, protocol, name, stype, domain,
            avahi.PROTO_UNSPEC, dbus.UInt32(0)))
        self.services[service.key()] = service

    def remove_service(self, interface, protocol, name, stype, domain):
        """Callback method to handle a service has going away.

        Removes the matching Service object if it exists.
        """
        
        try:
            del self.services[(interface, protocol, name, stype, domain)]
        except KeyError:
            pass

    def all_for_now(self):
        """A callback to handle the 'all for now' signal.

        This signal tells us that we now have all the service entires
        of the types we asked for, that avahi presently knows about.

        Exits the mainloop, returning control back to where the loop was
        first run.
        """
        self.loop.quit()


def get_host(service, use_host_names):
    """Returns the fully qualified host name, or IP address if the
    host name looks suspicious, or is preferred."""
    if (use_host_names and
        re.match("^([0-9a-z][0-9a-z\-]*\.)*([0-9a-z][0-9a-z\-]*)\.?",
                 service.host)):
        return service.host        
    
    return service.address
    
def make_url(service, scheme, use_host_names):
    """Generate a URL from service data."""
    # FIXME -- this isn't really flexible enough to account for a lot
    # of different URL types.
    
    host = get_host(service, use_host_names)

    user = ""
    password = ""
    
    for k in service.txt:
        if k.startswith("user="):  user = k[5:]        
    for k in service.txt:
        if k.startswith("password="): password = k[9:]
    if password:
        user += ":" + password
    if len(user): user = "@" + user

    path = ""
    for k in service.txt:
        if k.startswith("path="): path = k[5:]
    if not path.startswith("/"):
        path = "/" + path

    return "%s://%s%s%s" % (scheme, user, host, path)

def ReturnHosts(service_name, return_addrs=True):
    # Provide the Glib mainloop, so signals work.
    loop = gobject.MainLoop()
    gobject.timeout_add(3000, loop.quit)

    browser = AvahiServices('local', loop)

    # Set up browsing for the service type the user is interested in.
    # We look up aliases, use the full _foo._prot form, or take a guess.
    if service_map.has_key(service_name):
        stype = service_map[service_name]['stype']
    else:        
        if service_name[0] == '_':
            stype = service_name
        else:
            stype = "_%s._tcp" % service_name
    browser.browse_service_type(stype)

    try:
        # Run the loop! This waits around until the avahi daemon sends
        # us messages about the services found, and gives us the
        # "all for now" message. Or the user gets bored and interupts the
        # process with ctrl-c.
        loop.run()
    except KeyboardInterrupt:
        pass

    r = []
    for s in browser.services:
        r.append(get_host(browser.services[s], not return_addrs))
    
    return r

def main(argv=None):
    global debug
    if argv == None:
        argv = sys.argv
        
    (options, args) = parser.parse_args()
    debug = options.debug
    
    if len(args) != 1:
        parser.print_help()
        return 1

    # Provide the Glib mainloop, so signals work.
    loop = gobject.MainLoop()
    gobject.timeout_add(options.timeout, loop.quit)

    browser = AvahiServices(options.domain, loop)

    # Set up browsing for the service type the user is interested in.
    # We look up aliases, use the full _foo._prot form, or take a guess.
    if service_map.has_key(args[0]):
        stype = service_map[args[0]]['stype']
    else:        
        if args[0][0] == '_':
            stype = args[0]
        else:
            stype = "_%s._tcp" % args[0]
    browser.browse_service_type(stype)

    try:
        # Run the loop! This waits around until the avahi daemon sends
        # us messages about the services found, and gives us the
        # "all for now" message. Or the user gets bored and interupts the
        # process with ctrl-c.
        loop.run()
    except KeyboardInterrupt:
        pass

    for s in browser.services:
        if options.output == "urls" and stype_map.has_key(stype):
            print make_url(browser.services[s],
                           stype_map[stype], options.use_host_names)
        else:
            print get_host(browser.services[s], options.use_host_names)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


