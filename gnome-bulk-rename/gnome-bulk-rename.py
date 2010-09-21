#!/usr/bin/env python

import sys
from optparse import OptionParser
import logging
import os

import pygtk
pygtk.require('2.0')
import gtk

from gnomebulkrenameapp import GnomeBulkRenameApp
import constants
import config


def main(argv=None):
    if argv is None:
        argv = sys.argv
    parser = OptionParser(usage="%prog", version="%prog " + constants.__version__, description="Bulk rename tool for GNOME")
    (dummy_opt, args) = parser.parse_args(args=argv[1:])
    
    gtk.gdk.threads_init()
    
    # logging
    logdir = os.path.join(config.config_dir, "log")
    if not os.path.isdir(logdir):
        os.makedirs(logdir)
    logfile =  os.path.join(logdir, constants.application_name + ".log")
    logger = logging.getLogger("gnome.bulk-rename")
    logger.setLevel(logging.DEBUG)
    handler = logging.handlers.TimedRotatingFileHandler(logfile, 'D', 7, 4)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s %(name)s [%(levelname)s]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    
    app = GnomeBulkRenameApp(args)
    gtk.main()

if __name__ == "__main__":
    sys.argv.extend(["file:///home/hb/aaaa he he ho", "file:///home/hb/aaaa_usb_stick_claus"])#, "file:///home/hb/menu.doc"])
    sys.exit(main(sys.argv))
