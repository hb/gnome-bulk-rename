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

from preview import PreviewNoop, PreviewTranslate
from markup import MarkupColor


class GnomeBulkRename(object):
    """GNOME bulk rename tool"""
    
    FILES_MODEL_COLUMNS = (str, str, str, str, object)
    FILES_MODEL_COLUMN_ORIGINAL = 0
    FILES_MODEL_COLUMN_PREVIEW = 1
    FILES_MODEL_COLUMN_MARKUP_ORIGINAL = 2
    FILES_MODEL_COLUMN_MARKUP_PREVIEW = 3
    FILES_MODEL_COLUMN_GFILE = 4
    
    TARGET_TYPE_URI_LIST = 80
    
    __ui = """<ui>
    <menubar name="Menubar">
        <menu action="file">
            <placeholder name="FileItems"/>
            <menuitem action="quit"/>
        </menu>
        <menu action="help">
            <placeholder name="HelpItems"/>
            <menuitem action="about"/>
        </menu>
    </menubar>
    <toolbar name="Toolbar">
      <placeholder name="ToolbarItems"/>
      <toolitem action="quit"/>
    </toolbar>
    </ui>"""

    
    def __init__(self, uris=None):
        """constructor"""
        # application name
        self._application_name = "gnome-bulk-rename"
        glib.set_application_name(self._application_name)

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
        actions = [("file", None, "_File"),
                   ("view", None, "_View"),
                   ("quit", gtk.STOCK_QUIT, "_Quit", "<Control>q", "Quit the Program", self._on_action_quit),
                   ("help", None, "_Help"),
                   ("about", gtk.STOCK_ABOUT, "About", None, "About this program", self._on_action_about)
                   ]
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
        vbox.pack_start(self._uimanager.get_widget("/Menubar"), False)
        vbox.pack_start(self._uimanager.get_widget("/Toolbar"), False)
        
        # filename list
        scrolledwin = gtk.ScrolledWindow()
        scrolledwin.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        vbox.pack_start(scrolledwin)       
        self._files_model = gtk.ListStore(*GnomeBulkRename.FILES_MODEL_COLUMNS)
        treeview = gtk.TreeView(self._files_model)
        treeview.drag_dest_set(gtk.DEST_DEFAULT_MOTION | gtk.DEST_DEFAULT_HIGHLIGHT | gtk.DEST_DEFAULT_DROP,
                  [('text/uri-list', 0, GnomeBulkRename.TARGET_TYPE_URI_LIST)], gtk.gdk.ACTION_COPY)
        treeview.connect("drag-data-received", self._on_drag_data_received)
        renderer = gtk.CellRendererText()
        # column "original"
        column = gtk.TreeViewColumn("original", renderer, markup=GnomeBulkRename.FILES_MODEL_COLUMN_MARKUP_ORIGINAL)
        column.set_expand(True)
        treeview.append_column(column)
        # column "preview"
        column = gtk.TreeViewColumn("preview", renderer, markup=GnomeBulkRename.FILES_MODEL_COLUMN_MARKUP_PREVIEW)
        column.set_expand(True)
        treeview.append_column(column)
        # done with columns
        treeview.set_headers_visible(True)
        scrolledwin.add(treeview)
        
        # hsep
        vbox.pack_start(gtk.HSeparator(), False, False, 4)
        
        # TODO: hhb: combo box
        vbox.pack_start(gtk.Label("foo"))

        # current preview and markup
        #self._current_preview = PreviewNoop(self.refresh)
        self._current_preview = PreviewTranslate(self.refresh, " ", "_")
        self._current_markup = MarkupColor()

        if uris:
            self._add_to_files_model(uris)
        
        # show everything
        self._window.show_all()


    def quit(self):
        """Quit the application"""
        self._window.destroy()
        

    def _on_action_quit(self, dummy=None):
        self.quit()


    def _on_action_about(self, dummy=None):
        """Credits dialog"""
        authors = ["Holger Berndt <hb@gnome.org>"]
        about = gtk.AboutDialog()
        about.set_version("v%s" % __version__)
        about.set_authors(authors)
        about.set_license("GNU Lesser General Public License v2.1")
        about.set_transient_for(self._window)
        about.connect("response", lambda dlg, unused: dlg.destroy())
        about.show()


    def _add_to_files_model(self, uris):
        """Adds a sequence of uris to the files model"""
        # checking for doubles
        files_to_add = []
        for uri in uris:
            new_file = gio.File(uri)
            if self._is_file_in_model(new_file):
                continue
            fileinfo = new_file.query_info(gio.FILE_ATTRIBUTE_STANDARD_EDIT_NAME)
            if fileinfo:
                filename = fileinfo.get_attribute_as_string(gio.FILE_ATTRIBUTE_STANDARD_EDIT_NAME)
                files_to_add.append([filename, "", "", "", new_file])

        # preview and markup
        self._current_preview.preview(files_to_add)
        self._current_markup.markup(files_to_add)

        # add to model
        for file in files_to_add:
            self._files_model.append(file)


    def refresh(self):
        """Re-calculate previews"""
        self._current_preview.preview(self._files_model)
        self._current_markup.markup(self._files_model)


    def _is_file_in_model(self, gfile):
        """Return True if the given gio.File is already in the files model, False otherwise"""
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
    (dummy_opt, args) = parser.parse_args(args=argv[1:])
    app = GnomeBulkRename(args)
    gtk.main()

if __name__ == "__main__":
    sys.argv.extend(["file:///home/hb/aaaa he he ho", "file:///home/hb/aaaa_usb_stick_claus"])
    sys.exit(main(sys.argv))
