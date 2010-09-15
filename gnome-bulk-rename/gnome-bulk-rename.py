#!/usr/bin/env python

__version__ = "0.0.1"

import sys
from optparse import OptionParser

import pygtk
pygtk.require('2.0')
import gtk

from gnomebulkrenameapp import GnomeBulkRenameApp

def main(argv=None):
    if argv is None:
        argv = sys.argv
    parser = OptionParser(usage="%prog", version="%prog " + __version__, description="Bulk rename tool for GNOME")
    (dummy_opt, args) = parser.parse_args(args=argv[1:])
    app = GnomeBulkRenameApp(args)
    gtk.main()

if __name__ == "__main__":
    sys.argv.extend(["file:///home/hb/aaaa he he ho", "file:///home/hb/aaaa_usb_stick_claus", "file:///home/hb/menu.doc"])
    sys.exit(main(sys.argv))
