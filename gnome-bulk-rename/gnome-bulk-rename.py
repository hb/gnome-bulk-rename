#!/usr/bin/env python

# Copyright (C) 2010 Holger Berndt <hb@gnome.org>
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#  
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public
# License along with this program; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

__version__ = "0.0.1"

import sys
from optparse import OptionParser

import pygtk
pygtk.require('2.0')
import glib
import gio
import gtk

import os
import os.path
import urllib
import logging
import logging.handlers


class GnomeBulkRename(object):
    """GNOME bulk rename tool"""
    
    FILES_MODEL_COLUMNS = (str, str, object)
    FILES_MODEL_COLUMN_ORIGINAL = 0
    FILES_MODEL_COLUMN_PREVIEW = 1
    FILES_MODEL_COLUMN_GFILE = 2
    
    TARGET_TYPE_URI_LIST = 80
    
    __ui = """<ui>
    <menubar name="Menubar">
        <menu action="file">
            <placeholder name="FileItems"/>
            <menuitem action="quit"/>
        </menu>
    </menubar>
    <toolbar name="Toolbar">
      <placeholder name="ToolbarItems"/>
      <toolitem action="quit"/>
    </toolbar>
    </ui>"""

    
    def __init__(self):
        """constructor"""
        # application name (used for paths etc)
        self._application_name = "gnome-bulk-rename"

        # logging
        logdir = os.path.join(glib.get_user_config_dir(), self._application_name, "log")
        if not os.path.isdir(logdir):
            os.makedirs(logdir)
        logfile =  os.path.join(logdir, self._application_name + ".log")
        self._logger = logging.getLogger("gnome.bulk-rename.bulk-rename")
        self._logger.setLevel(logging.DEBUG)
        handler = logging.handlers.TimedRotatingFileHandler(logfile, 'D', 7, 4)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s %(name)s [%(levelname)s]: %(message)s")
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)
        self._logger.debug("init")
        
        # actions
        self._uimanager = gtk.UIManager()
        self._action_group = gtk.ActionGroup("mainwindow")
        actions = [('file', None, '_File'),
                   ('view', None, '_View'),
                   ('quit', gtk.STOCK_QUIT, '_Quit', "<Control>q", 'Quit the Program', self.quit)]
        self._action_group.add_actions(actions)
        self._uimanager.insert_action_group(self._action_group)
        self._uimanager.add_ui_from_string(self.__ui)

        # window
        self._window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self._window.set_size_request(500, 300)
        self._window.connect("destroy", gtk.main_quit)
        self._window.add_accel_group(self._uimanager.get_accel_group())
        
        vbox = gtk.VBox(False, 0)
        self._window.add(vbox)

        # menu bar
        vbox.pack_start(self._uimanager.get_widget("/Toolbar"), False)
        
        # filename list
        scrolledwin = gtk.ScrolledWindow()
        scrolledwin.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        vbox.pack_start(scrolledwin)
        
        self._files_model = gtk.ListStore(*GnomeBulkRename.FILES_MODEL_COLUMNS)
        treeview = gtk.TreeView(self._files_model)
        treeview.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                  gtk.DEST_DEFAULT_HIGHLIGHT | gtk.DEST_DEFAULT_DROP,
                  [('text/uri-list', 0, GnomeBulkRename.TARGET_TYPE_URI_LIST)], gtk.gdk.ACTION_COPY)
        treeview.connect("drag-data-received", self._on_drag_data_received)
        renderer = gtk.CellRendererText()
        # column "original"
        column = gtk.TreeViewColumn("original", renderer, text=GnomeBulkRename.FILES_MODEL_COLUMN_ORIGINAL)
        treeview.append_column(column)
        # column "preview"
        column = gtk.TreeViewColumn("preview", renderer, text=GnomeBulkRename.FILES_MODEL_COLUMN_PREVIEW)
        treeview.append_column(column)
        # done with columns
        treeview.set_headers_visible(True)
        scrolledwin.add(treeview)
        
        # show everything
        self._window.show_all()


    def quit(self, dummy=None):
        """Quit the application"""
        self._window.destroy()


    def _add_to_files_model(self, uris):
        """Adds a sequence of uris to the files model"""
        # add files to model, checking for doubles first
        files_to_add = []
        for uri in uris:
            new_file = gio.File(uri)
            if self._is_file_in_model(new_file):
                continue
            fileinfo = new_file.query_info(gio.FILE_ATTRIBUTE_STANDARD_EDIT_NAME)
            if fileinfo:
                filename = fileinfo.get_attribute_as_string(gio.FILE_ATTRIBUTE_STANDARD_EDIT_NAME)
                files_to_add.append([filename, filename, new_file])
        # TODO: rename preview
        for file in files_to_add:
            self._files_model.append(file)


    def _is_file_in_model(self, gfile):
        """Return True if the gfile is already in the files model, False otherwise"""
        for row in self._files_model:
            if row[GnomeBulkRename.FILES_MODEL_COLUMN_GFILE].equal(gfile):
                return True
        return False


    def _on_drag_data_received(self, widget, context, x, y, selection, target_type, timestamp):
        """Callback for received drag data"""
        if target_type == GnomeBulkRename.TARGET_TYPE_URI_LIST:
            uris = selection.data.strip("\r\n\x00")
            uri_splitted = uris.split()
            self._add_to_files_model(uris.split())


def main(argv=None):
    if argv is None:
        argv = sys.argv
    parser = OptionParser(usage="%prog", version="%prog " + __version__, description="Bulk rename tool for GNOME")
    (dummy_opt, dummy_args) = parser.parse_args(args=argv[1:])

    app = GnomeBulkRename()
    gtk.main()

if __name__ == "__main__":
    sys.exit(main(sys.argv))
