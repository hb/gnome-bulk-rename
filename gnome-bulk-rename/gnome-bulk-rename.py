#!/usr/bin/env python

import sys
from optparse import OptionParser
import logging
import os

import pygtk
pygtk.require('2.0')
import gtk

from gnomebulkrenameapp import GnomeBulkRenameApp, GnomeBulkRenameAppSimple
import constants
import config


def main(argv=None):

    # argument parsing
    if argv is None:
        argv = sys.argv
    parser = OptionParser(usage="%prog", version="%prog " + constants.__version__, description="Bulk rename tool for GNOME")
    parser.add_option("-s", "--simple", action="store_true")
    (opt, args) = parser.parse_args(args=argv[1:])

    # init
    gtk.gdk.threads_init()
    
    # logging
    logdir = os.path.join(config.config_dir, "log")
    if not os.path.isdir(logdir):
        os.makedirs(logdir)
    logfilename = constants.application_name
    if opt.simple:
        logfilename += "-simple"
    logfile =  os.path.join(logdir, logfilename + ".log")
    logger = logging.getLogger("gnome.bulk-rename")
    logger.setLevel(logging.DEBUG)
    handler = logging.handlers.TimedRotatingFileHandler(logfile, 'D', 7, 4)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s %(name)s [%(levelname)s]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # start the application
    if opt.simple:
        app = GnomeBulkRenameAppSimple(args)
    else:
        app = GnomeBulkRenameApp(args)
    gtk.main()

if __name__ == "__main__":
#    sys.argv.extend(["--simple", "file:///home/hb/aaaa he he ho", "file:///home/hb/aaaa_usb_stick_claus", "file:///home/hb/aaaa he he ho", "file:///home/hb/menu.doc"])
    sys.argv.extend(["file:///home/hb/aaaa he he ho", "file:///home/hb/aaaa_usb_stick_claus", "file:///home/hb/aaaa he he ho", "file:///home/hb/menu.doc"])
    sys.exit(main(sys.argv))
