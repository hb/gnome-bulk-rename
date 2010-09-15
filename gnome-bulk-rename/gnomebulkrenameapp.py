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

import cPickle as pickle

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

from preview import PreviewNoop
from markup import MarkupColor
import check
import constants

def clear_gtk_container(container):
    """Remove all children from a GtkContainer"""
    container.foreach(lambda child, cont : cont.remove(child), container)


class GnomeBulkRenameApp(object):
    """GNOME bulk rename tool"""
    
    
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

        # config dir
        self._configdir = os.path.join(glib.get_user_config_dir(), self._application_name)

        # logging
        logdir = os.path.join(self._configdir, "log")
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
        self._window.connect("delete-event", self._on_delete_event)
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
        self._files_model = gtk.ListStore(*constants.FILES_MODEL_COLUMNS)
        treeview = gtk.TreeView(self._files_model)
        treeview.drag_dest_set(gtk.DEST_DEFAULT_MOTION | gtk.DEST_DEFAULT_HIGHLIGHT | gtk.DEST_DEFAULT_DROP,
                  [('text/uri-list', 0, GnomeBulkRenameApp.TARGET_TYPE_URI_LIST)], gtk.gdk.ACTION_COPY)
        treeview.connect("drag-data-received", self._on_drag_data_received)
        treeview.get_selection().set_mode(gtk.SELECTION_NONE)
        textrenderer = gtk.CellRendererText()
        pixbufrenderer = gtk.CellRendererPixbuf()
        # column "original"
        column = gtk.TreeViewColumn("original", textrenderer, markup=constants.FILES_MODEL_COLUMN_MARKUP_ORIGINAL)
        column.set_expand(True)
        treeview.append_column(column)
        # column "preview"
        column = gtk.TreeViewColumn("preview", textrenderer, markup=constants.FILES_MODEL_COLUMN_MARKUP_PREVIEW)
        column.set_expand(True)
        treeview.append_column(column)
        # column icon
        column = gtk.TreeViewColumn("", pixbufrenderer, stock_id=constants.FILES_MODEL_COLUMN_ICON_STOCK)
        column.set_expand(False)
        treeview.append_column(column)
        # done with columns
        treeview.set_headers_visible(True)
        # tooltip
        treeview.set_tooltip_column(constants.FILES_MODEL_COLUMN_TOOLTIP)
        scrolledwin.add(treeview)
        
        # info bar
        self._files_info_bar = gtk.InfoBar()
        self._files_info_bar.set_no_show_all(True)
        vbox.pack_start(self._files_info_bar, False)

        # hsep
        vbox.pack_start(gtk.HSeparator(), False, False, 4)

        # current preview and markup
        self._current_preview = PreviewNoop(self.refresh)
        self._current_markup = MarkupColor()
        
        # hbox
        hbox = gtk.HBox(False, 4) 
        vbox.pack_start(hbox, False)
        
        # previews selection
        previews_model = gtk.ListStore(*constants.PREVIEWS_SELECTION_COLUMNS)
        self._previews_combobox = gtk.ComboBox(previews_model)
        cell = gtk.CellRendererText()
        self._previews_combobox.pack_start(cell, True)
        self._previews_combobox.add_attribute(cell, "text", 0)
        self._previews_combobox.connect("changed", self._on_previews_combobox_changed)
        hbox.pack_start(self._previews_combobox)

        self._collect_previews()
        
        # rename button
        self._rename_button = gtk.Button("Rename")
        self._rename_button.connect("clicked", self._on_rename_button_clicked)
        hbox.pack_start(self._rename_button, False)

        # add files
        if uris:
            self._add_to_files_model(uris)
        
        # restore state
        self._restore_state()
        
        # show everything
        self._window.show_all()


    def quit(self):
        """Quit the application"""
        self._save_state()
        self._logger.debug("quit")
        self._window.destroy()

    
    def _save_state(self):
        self._logger.debug("Saving state")
        state = {}
        
        # combo box
        previews_model = self._previews_combobox.get_model()
        idx = self._previews_combobox.get_active()
        if idx >= 0:
            state["current_preview_short_description"] = previews_model[idx][0] 
            
        pickle.dump(state, open(os.path.join(self._configdir, "state"), "w"))


    def _restore_state(self):
        # state restore
        statesavefilename = os.path.join(self._configdir, "state")
        if not os.path.isfile(statesavefilename):
            return
        
        self._logger.debug("Restoring state")
        state = pickle.load(open(statesavefilename, "r"))
        
        # previews combo box
        tar = 0 
        if "current_preview_short_description" in state:
            desc = state["current_preview_short_description"]
            for ii, row in enumerate(self._previews_combobox.get_model()):
                if row[0] == desc:
                    tar = ii
                    break
        self._previews_combobox.set_active(tar)


    def _on_action_quit(self, dummy=None):
        self.quit()

    def _on_delete_event(self, widget, event):
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


    def _on_rename_button_clicked(self, button):
        print 'TODO rename button clicked'


    def _on_previews_combobox_changed(self, combobox):
        previewclass = combobox.get_model()[combobox.get_active()][constants.PREVIEWS_SELECTION_PREVIEW]
        self._current_preview = previewclass(self.refresh)
        self.refresh()


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
                files_to_add.append([filename, "", "", "", new_file, None, None])


        # add to model
        for file in files_to_add:
            self._files_model.append(file)

        # checks
        self.refresh()


    def refresh(self):
        """Re-calculate previews"""
        self._current_preview.preview(self._files_model)
        self._current_markup.markup(self._files_model)
        self.check_targets()


    def check_targets(self):
        """Some sanity check if renaming can possibly work"""
        check.clear_warnings_errors(self._files_model)
        highest_level_double_targets = check.check_for_double_targets(self._files_model)
        highest_level_existing_names = check.check_for_already_existing_names(self._files_model)
        self._set_highest_problem_level(max(highest_level_double_targets, highest_level_existing_names))


    def _set_highest_problem_level(self, highest_level):
        if highest_level == 0:
            self._files_info_bar.hide()
            self._rename_button.set_sensitive(True)
            return

        # clean up
        content_area = self._files_info_bar.get_content_area()
        clear_gtk_container(content_area)
        action_area = self._files_info_bar.get_action_area()
        clear_gtk_container(action_area)
            
        if highest_level == 1:
            label = gtk.Label("Expect problems when trying to rename")
            label.show()
            content_area.pack_start(label, False)
            self._files_info_bar.set_message_type(gtk.MESSAGE_WARNING)
            self._files_info_bar.show()
            self._rename_button.set_sensitive(True)
        elif highest_level == 2:
            label = gtk.Label("Rename not possible")
            label.show()
            content_area = self._files_info_bar.get_content_area()
            clear_gtk_container(content_area)
            content_area.pack_start(label, False)
            self._files_info_bar.set_message_type(gtk.MESSAGE_ERROR)
            self._files_info_bar.show()
            self._rename_button.set_sensitive(False)


    def _is_file_in_model(self, gfile):
        """Return True if the given gio.File is already in the files model, False otherwise"""
        for row in self._files_model:
            if row[constants.FILES_MODEL_COLUMN_GFILE].equal(gfile):
                return True
        return False


    def _on_drag_data_received(self, widget, context, x, y, selection, target_type, timestamp):
        """Callback for received drag data"""
        if target_type == GnomeBulkRenameApp.TARGET_TYPE_URI_LIST:
            uris = selection.data.strip("\r\n\x00")
            uri_splitted = uris.split()
            self._add_to_files_model(uris.split())


    def _collect_previews(self):
        """Fill combobox with previews"""
        previews_model = self._previews_combobox.get_model()
        
        # builtin
        for preview in self._get_previews_from_model_by_introspection("preview"):
            previews_model.append((preview.short_description, preview))


    def _get_previews_from_model_by_introspection(self, modulename):
        """Look for previewable objects in the module named modulename"""
        try:
            module = __import__(modulename)
        except ImportError:
            self._logger.error("Could not import module file: " + modulename)
            return []

        self._logger.debug("Inspecting module " + modulename)
        previews = []
        for entry in dir(module):
            if entry.startswith("_"):
                continue
            classobj = getattr(module, entry)
            if hasattr(classobj, "preview") and hasattr(classobj, "short_description"):
                try:
                    if classobj.skip:
                        continue
                except AttributeError:
                    pass
                previews.append(classobj)

        self._logger.debug(("`Found %d preview objects: " % len(previews))+ ", ".join([repr(previewtype) for previewtype in previews]))
        return previews
