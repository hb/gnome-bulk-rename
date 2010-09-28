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

import os
import sys
import os.path
import urllib
import logging
import logging.handlers
import subprocess

import pygtk
pygtk.require('2.0')
import glib
import gio
import gtk

from preview import PreviewNoop,PreviewReplaceLongestSubstring, PreviewCommonModificationsSimple
from markup import MarkupColor
import check
import constants
import rename
import undo
import gtkutils
import collect
import config
import preferences


class GnomeBulkRenameAppBase(object):
    """Base class for bulk renamer frontends"""

    TARGET_TYPE_URI_LIST = 94
    TARGET_TYPE_MODEL_ROW = 95

    def __init__(self, uris=None):

        def files_model_row_deleted_cb(model, path, self):
            # setting sensitive again happens in the refresh logic
            if len(model) == 0:
                self._rename_button.set_sensitive(False)

        # undo stack
        self._undo = undo.Undo()

        # set up filename list widget with infobar
        # subclasses can pack this where they want
        self._file_list_widget = gtk.VBox(False, 0)

        # rename button widget
        self._rename_button = gtk.Button()
        button_hbox = gtk.HBox(False, 2)
        button_hbox.pack_start(gtk.image_new_from_stock(gtk.STOCK_CONVERT, gtk.ICON_SIZE_BUTTON))
        button_hbox.pack_start(gtk.Label("Rename"))
        self._rename_button.add(button_hbox)
        self._rename_button.connect("clicked", self._on_rename_button_clicked)

        # info bar
        self._files_info_bar = gtk.InfoBar()
        self._files_info_bar.connect("response", self._on_files_info_bar_response)
        self._files_info_bar.set_no_show_all(True)
        self._file_list_widget.pack_start(self._files_info_bar, False)

        # filename list
        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        self._file_list_widget.pack_start(frame, True, True, 4)
        scrolledwin = gtk.ScrolledWindow()
        scrolledwin.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        frame.add(scrolledwin)
        self._files_model = gtk.ListStore(*constants.FILES_MODEL_COLUMNS)
        self._files_model.connect("row-deleted", files_model_row_deleted_cb, self)
        treeview = gtk.TreeView(self._files_model)
        treeview.set_size_request(450, 100)
        row_targets = [('text/uri-list', gtk.TARGET_OTHER_APP, GnomeBulkRenameAppBase.TARGET_TYPE_URI_LIST),
                        ("GTK_TREE_MODEL_ROW", gtk.TARGET_SAME_WIDGET, GnomeBulkRenameAppBase.TARGET_TYPE_MODEL_ROW)]
        treeview.enable_model_drag_source(gtk.gdk.BUTTON1_MASK, row_targets, gtk.gdk.ACTION_MOVE)
        treeview.enable_model_drag_dest(row_targets, gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        treeview.connect("drag-data-received", self._on_drag_data_received)
        selection = treeview.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        selection.connect("changed", self._on_tree_selection_changed)
        textrenderer = gtk.CellRendererText()
        pixbufrenderer = gtk.CellRendererPixbuf()
        # column icon
        column = gtk.TreeViewColumn("", pixbufrenderer, stock_id=constants.FILES_MODEL_COLUMN_ICON_STOCK)
        column.set_expand(False)
        treeview.append_column(column)
        # column "original"
        column = gtk.TreeViewColumn("original", textrenderer, markup=constants.FILES_MODEL_COLUMN_MARKUP_ORIGINAL)
        column.set_expand(True)
        treeview.append_column(column)
        # column "preview"
        column = gtk.TreeViewColumn("preview", textrenderer, markup=constants.FILES_MODEL_COLUMN_MARKUP_PREVIEW)
        column.set_expand(True)
        treeview.append_column(column)
        # done with columns
        treeview.set_headers_visible(True)
        # tooltip
        treeview.set_tooltip_column(constants.FILES_MODEL_COLUMN_TOOLTIP)
        scrolledwin.add(treeview)
        self._files_treeview = treeview
        
        # current preview and markup
        self._current_preview = PreviewNoop(self.refresh, self._files_model)
        self._current_markup = MarkupColor()

        # checker
        self._checker = None

        # add files
        if uris:
            self._add_to_files_model(uris)


    def refresh(self, did_just_rename=False, model_changed=False):
        """Re-calculate previews"""
        if did_just_rename or model_changed:
            try:
                self._current_preview.post_rename(self._files_model)
            except AttributeError:
                pass

        # preview if valid
        try:
            valid = self._current_preview.valid
        except AttributeError:
            valid = True
        
        if valid:
            try:
                self._current_preview.preview(self._files_model)
            except Exception, ee:
                valid = False
        
        # reset if an error occured or invalid in the first place
        if not valid:
            for row in self._files_model:
                row[1] = row[0]
                
        # markup
        self._current_markup.markup(self._files_model)
        
        if not did_just_rename:
            self._checker = check.Checker(self._files_model)
            self._checker.perform_checks()
            self._update_rename_button_sensitivity()
            self._set_info_bar_according_to_problem_level(self._checker.highest_problem_level)

    def _on_tree_selection_changed(self, selection):
        self._remove_action.set_sensitive(selection.count_selected_rows() > 0)

    def _on_rename_button_clicked(self, button):
        self._logger.debug("Starting rename operation")
        self._checker.clear_all_warnings_and_errors()
        # TODO throttle on
        self._files_info_bar.hide()
        rename.Rename(self._files_model, len(self._checker.circular_uris) > 0, self._on_rename_completed)


    def _on_drag_data_received(self, widget, context, x, y, selection, target_type, timestamp):
        """Callback for received drag data"""
        if target_type == GnomeBulkRenameAppBase.TARGET_TYPE_URI_LIST:
            uris = selection.data.strip("\r\n\x00")
            uri_splitted = uris.split()
            self._add_to_files_model(uris.split())


    def _on_files_info_bar_response(self, info_bar, response_id):
        
        if (response_id == constants.FILES_INFO_BAR_RESPONSE_ID_INFO_WARNING) or (response_id == constants.FILES_INFO_BAR_RESPONSE_ID_INFO_ERROR):
            problems = set()
            for row in self._files_model:
                if row[constants.FILES_MODEL_COLUMN_TOOLTIP]:
                    for entry in row[constants.FILES_MODEL_COLUMN_TOOLTIP].split("\n"):
                        if entry.startswith("<b>ERROR") or entry.startswith("<b>WARNING"):
                            problems.add(entry)
            if problems:
                if response_id == constants.FILES_INFO_BAR_RESPONSE_ID_INFO_WARNING:
                    dlg_type = gtk.MESSAGE_WARNING
                    msg = "The following problems might prevent renaming:"
                else:
                     dlg_type = gtk.MESSAGE_ERROR
                     msg = "The following problems prevent renaming:" 
                dlg = gtk.MessageDialog(parent=self._window, type=dlg_type, buttons=gtk.BUTTONS_CLOSE, message_format=msg)
                dlg.format_secondary_markup("\n".join(problems))
                dlg.show_all()
                dlg.run()
                dlg.destroy()


    def _add_to_files_model(self, uris):
        """Adds a sequence of uris to the files model"""
        def __get_uri_dirname(gfile):
            uri = gfile.get_uri()
            # remove trailing slash
            if uri[-1] == "/":
                uri = uri[0:-1]
            # find last slash
            idx = uri.rfind("/")
            if idx != -1:
                dirname = uri[0:idx]
            else:
                raise ValueError
            return dirname + "/"
            

        # get GFiles for uris
        gfiles = [gio.File(uri) for uri in uris]
        # make sure they don't refer to identical uris (back and forth for normalization inside GFile)
        uris = set()
        for gfile in gfiles:
            uris.add(gfile.get_uri())
        gfiles = [gio.File(uri) for uri in uris]
        
        files_to_add = []
        for gfile in gfiles:
            # checking for already existing files
            if self._is_file_in_model(gfile):
                continue
            fileinfo = gfile.query_info(gio.FILE_ATTRIBUTE_STANDARD_EDIT_NAME)
            if fileinfo:
                filename = fileinfo.get_attribute_as_string(gio.FILE_ATTRIBUTE_STANDARD_EDIT_NAME)
                try:
                    dirname = __get_uri_dirname(gfile)
                except ValueError:
                    self._logger.error("Cannot add URI because it contains no slash: '%s'" % gfile.get_uri())
                    continue
                files_to_add.append([filename, "", "", "", gfile, None, None, dirname])


        # add to model
        for file in files_to_add:
            self._files_model.append(file)

        self.refresh(model_changed=True)


    def _is_file_in_model(self, gfile):
        """Return True if the given gio.File is already in the files model, False otherwise"""
        for row in self._files_model:
            if row[constants.FILES_MODEL_COLUMN_GFILE].equal(gfile):
                return True
        return False


    def _update_rename_button_sensitivity(self):
        sensitive = True

        if self._checker and ((self._checker.all_names_stay_the_same) or (self._checker.highest_problem_level > 1)):
            sensitive = False

        self._rename_button.set_sensitive(sensitive)


    def _set_info_bar_according_to_problem_level(self, highest_level):
        
        if highest_level == 0:
            self._files_info_bar.hide()
            return

        content_area = self._files_info_bar.get_content_area()
        gtkutils.clear_gtk_container(content_area)
        action_area = self._files_info_bar.get_action_area()
        gtkutils.clear_gtk_container(action_area)

        hbox = gtk.HBox(False, 4)
        
        if highest_level == 1:
            hbox.pack_start(gtk.image_new_from_stock(gtk.STOCK_DIALOG_WARNING, gtk.ICON_SIZE_LARGE_TOOLBAR))
            hbox.pack_start(gtk.Label("Expect problems when trying to rename"))
            hbox.show_all()
            content_area.pack_start(hbox, False)
            self._files_info_bar.set_message_type(gtk.MESSAGE_WARNING)
            self._files_info_bar.add_button(gtk.STOCK_INFO, constants.FILES_INFO_BAR_RESPONSE_ID_INFO_WARNING)
            self._files_info_bar.show()
            
        elif highest_level == 2:
            hbox.pack_start(gtk.image_new_from_stock(gtk.STOCK_DIALOG_ERROR, gtk.ICON_SIZE_LARGE_TOOLBAR))
            hbox.pack_start(gtk.Label("Rename not possible"))
            hbox.show_all()
            content_area = self._files_info_bar.get_content_area()
            gtkutils.clear_gtk_container(content_area)
            content_area.pack_start(hbox, False)
            self._files_info_bar.set_message_type(gtk.MESSAGE_ERROR)
            self._files_info_bar.add_button(gtk.STOCK_INFO, constants.FILES_INFO_BAR_RESPONSE_ID_INFO_ERROR)
            self._files_info_bar.show()


    def _set_info_bar_according_to_rename_operation(self, num_renames, num_errors, was_undo):

        content_area = self._files_info_bar.get_content_area()
        gtkutils.clear_gtk_container(content_area)
        action_area = self._files_info_bar.get_action_area()
        gtkutils.clear_gtk_container(action_area)
        
        hbox = gtk.HBox(False, 4)
        
        if num_errors > 0:
            hbox.pack_start(gtk.image_new_from_stock(gtk.STOCK_DIALOG_WARNING, gtk.ICON_SIZE_LARGE_TOOLBAR), False)
            self._files_info_bar.set_message_type(gtk.MESSAGE_WARNING)
            if not was_undo:
                hbox.pack_start(gtk.Label("Problems occured during rename"), False)
            else:
                hbox.pack_start(gtk.Label("Problems occured during undo"), False)
        else:
            self._files_info_bar.set_message_type(gtk.MESSAGE_INFO)
            if not was_undo:
                hbox.pack_start(gtk.Label("Files successfully renamed"), False)
            else:
                hbox.pack_start(gtk.Label("Undo successful"), False)
        
        hbox.show_all()
        content_area.pack_start(hbox, False)
        
        # undo button
        if num_renames > 0:
            if not was_undo:
                button = gtk.Button(stock=gtk.STOCK_UNDO)
                button.connect("clicked", self._on_undo_button_clicked)
            else:
                button = gtk.Button(stock=gtk.STOCK_REDO)
                button.connect("clicked", self._on_redo_button_clicked)
            button.show()
            action_area.pack_start(button)
                
        
        self._files_info_bar.show()        


    def _on_rename_completed(self, num_renames, num_errors, results):
        self._logger.debug("Rename completed")
        
        undo_action = rename.RenameUndoAction(results)
        undo_action.set_done_callback(self._on_undo_rename_completed)
        self._undo.push(undo_action)
        
        self.refresh(did_just_rename=True)
        self._set_info_bar_according_to_rename_operation(num_renames, num_errors, False)
        # TODO throttle off


    def _on_undo_rename_completed(self, num_renames, num_errors, undo_action):
        self._logger.debug("Undo rename done")
        if num_renames > 0:
            undo_action.set_done_callback(self._on_redo_rename_completed)
            self._undo.push_to_redo(undo_action)
        self.refresh(did_just_rename=True)
        self._set_info_bar_according_to_rename_operation(num_renames, num_errors, True)
        

    def _on_redo_rename_completed(self, num_renames, num_errors, undo_action):
        self._logger.debug("Redo rename done")
        if num_renames > 0:
            undo_action.set_done_callback(self._on_undo_rename_completed)
            self._undo.push_back_to_undo(undo_action)
        self.refresh(did_just_rename=True)
        self._set_info_bar_according_to_rename_operation(num_renames, num_errors, False)


    def _on_undo_button_clicked(self, button):
        self._logger.debug('undo clicked')
        self._undo.undo()


    def _on_redo_button_clicked(self, button):
        self._logger.debug('redo clicked')
        self._undo.redo()


class GnomeBulkRenameAppSimple(GnomeBulkRenameAppBase):
    """Simplified GNOME bulk rename tool"""

    def __init__(self, uris=None):
        GnomeBulkRenameAppBase.__init__(self, uris)

        glib.set_application_name(constants.application_name + "-simple")

        self._logger = logging.getLogger("gnome.bulk-rename.bulk-rename-simple")
        self._logger.debug("init")

        # window
        self._window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self._window.set_title("Simple Bulk Rename")
        self._window.set_border_width(4)
        self._window.connect("destroy", gtk.main_quit)
        self._window.connect("delete-event", self._on_delete_event)

        # main vbox
        vbox = gtk.VBox(False, 0)
        self._window.add(vbox)

        # description
        hbox = gtk.HBox(False, 0)
        hbox.pack_start(gtk.image_new_from_stock(gtk.STOCK_DIALOG_INFO, gtk.ICON_SIZE_DIALOG), False)
        hbox.pack_start(gtk.Label("You can choose among some common rename operations,\nor press the 'Advanced' button for more options."), False)
        vbox.pack_start(hbox, False)

        # add file list
        vbox.pack_start(self._file_list_widget)

        # hsep
        vbox.pack_start(gtk.HSeparator(), False, False, 4)

        # create previewer, and add config
        # first, try "longest common substring"
        self._current_preview = PreviewReplaceLongestSubstring(self.refresh, self._files_model)
        # if that doesn't work, offer some common simple modifications
        if not self._current_preview.valid:
            self._logger.debug("URIs don't have a common substring, offer simple modifications instead.")
            self._current_preview = PreviewCommonModificationsSimple(self.refresh, self._files_model)
        self.refresh()
        
        vbox.pack_start(self._current_preview.get_config_widget(), False)
        
        # hsep
        vbox.pack_start(gtk.HSeparator(), False, False, 4)
        
        # rename, cancel, and more buttons
        buttonbox = gtk.HButtonBox()
        buttonbox.set_layout(gtk.BUTTONBOX_END)
        buttonbox.set_spacing(12)
        vbox.pack_start(buttonbox, False)

        advanced_button = gtk.Button("Advanced")
        advanced_button.connect("clicked", self._on_advanced_button_clicked)
        buttonbox.add(advanced_button)

        cancel_button = gtk.Button(stock=gtk.STOCK_CANCEL)
        cancel_button.connect("clicked", lambda button, self : self.quit(), self)
        buttonbox.add(cancel_button)        

        buttonbox.add(self._rename_button)
        
        try:
            self._current_preview.grab_focus()
        except AttributeError:
            pass
        
        self._window.show_all()


    def quit(self):
        self._logger.debug("quit")
        self._window.destroy()

    def _on_advanced_button_clicked(self, button):
        cmd = [row[constants.FILES_MODEL_COLUMN_GFILE].get_uri() for row in self._files_model]
        cmd.insert(0, "/home/hb/src/gnome-bulk-rename/gnome-bulk-rename/gnome-bulk-rename3.py") # TODO
        try:
            subprocess.Popen(cmd)
        except OSError, ee:
            self._logger.error("Command invokation failed: '%s'" % "".join(cmd))
            # open an error dialog
            dlg = gtk.MessageDialog(self._window, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE)
            dlg.set_title("Switch failed")
            dlg.set_markup("<b>Switch to advanced mode failed</b>")
            dlg.format_secondary_markup("The command '%s' could not be found." % cmd[0])
            dlg.run()
            dlg.destroy()
        else:
            self._logger.debug("Executed '%s', will now quit" % " ".join(cmd))
            self.quit()
        

    def _on_delete_event(self, widget, event):
        self.quit()
        return True


class GnomeBulkRenameApp(GnomeBulkRenameAppBase):
    """GNOME bulk rename tool"""
        
    __ui = """<ui>
    <menubar name="Menubar">
        <menu action="file">
            <placeholder name="FileItems"/>
            <menuitem action="quit"/>
        </menu>
        <menu action="edit">
            <placeholder name="EditItems"/>
            <menuitem action="%(undoaction)s"/>
            <menuitem action="%(redoaction)s"/>
            <separator/>
            <menuitem action="add"/>
            <menuitem action="addfolders"/>
            <menuitem action="remove"/>
            <menuitem action="clear"/>
            <separator/>
            <menuitem action="preferences"/>
        </menu>
        <menu action="help">
            <placeholder name="HelpItems"/>
            <menuitem action="about"/>
        </menu>
    </menubar>
    <toolbar name="Toolbar">
      <placeholder name="ToolbarItems"/>
      <toolitem action="add"/>
      <toolitem action="remove"/>
      <toolitem action="clear"/>
      <toolitem action="preferences"/>
      <toolitem action="quit"/>
    </toolbar>
    </ui>""" % {
        "undoaction" : undo.Undo.UNDO_ACTION_NAME,
        "redoaction" : undo.Undo.REDO_ACTION_NAME,
        }

    
    def __init__(self, uris=None):
        """constructor"""
        GnomeBulkRenameAppBase.__init__(self, uris)

        def sorting_combobox_changed(combobox, files_model, order_check, config_container):
            id = combobox.get_model()[combobox.get_active()][constants.SORTING_COLUMN_ID]
            instance = combobox.get_model()[combobox.get_active()][constants.SORTING_COLUMN_INSTANCE]
            if order_check.get_active():
                order = gtk.SORT_DESCENDING
            else:
                order = gtk.SORT_ASCENDING

            gtkutils.clear_gtk_container(config_container)

            if id == constants.SORT_ID_MANUAL:
                order_check.set_sensitive(False)
                files_model.set_sort_column_id(gtk.TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID, order)
            else:
                order_check.set_sensitive(True)
                if hasattr(inst, "get_config_widget"):
                    config_container.pack_start(inst.get_config_widget(), False)
                    config_container.show_all()
                files_model.set_sort_column_id(id, order)

        def sorting_order_check_toggled(checkbutton, model, combobox, config_container):
            sorting_combobox_changed(combobox, model, checkbutton, config_container)


        # application name
        glib.set_application_name(constants.application_name)

        self._logger = logging.getLogger("gnome.bulk-rename.bulk-rename")
        self._logger.debug("init")
        
        # actions
        self._uimanager = gtk.UIManager()
        self._action_group = gtk.ActionGroup("mainwindow")
        actions = [("file", None, "_File"),
                   ("edit", None, "_Edit"),
                   ("view", None, "_View"),
                   ("add", gtk.STOCK_ADD, "Add files", None, "Add files to the list", self._on_action_add),
                   ("addfolders", None, "Add folders", None, "Add folders to the list", self._on_action_add_folders),
                   ("remove", gtk.STOCK_REMOVE, "Remove files", None, "Remove selected files from the list", self._on_action_remove),
                   ("clear", gtk.STOCK_CLEAR, "Clear", None, "Removes all files from the list", self._on_action_clear),
                   ("preferences", gtk.STOCK_PREFERENCES, "Preferences", None, "Preferences", self._on_action_preferences),
                   ("quit", gtk.STOCK_QUIT, "_Quit", "<Control>q", "Quit the Program", self._on_action_quit),
                   ("help", None, "_Help"),
                   ("about", gtk.STOCK_ABOUT, "About", None, "About this program", self._on_action_about)
                   ]
        self._action_group.add_actions(actions)
        self._action_group.add_action(self._undo.get_undo_action())
        self._action_group.add_action(self._undo.get_redo_action())
        self._uimanager.insert_action_group(self._action_group)
        self._uimanager.add_ui_from_string(self.__ui)
        self._remove_action = self._action_group.get_action("remove")
        self._remove_action.set_sensitive(False)

        # window
        self._window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self._window.set_title("Bulk Rename")
        self._window.set_size_request(450, 600)
        self._window.set_border_width(4)
        self._window.connect("destroy", gtk.main_quit)
        self._window.connect("delete-event", self._on_delete_event)
        self._window.add_accel_group(self._uimanager.get_accel_group())
        
        vbox = gtk.VBox(False, 0)
        self._window.add(vbox)

        # menu bar
        vbox.pack_start(self._uimanager.get_widget("/Menubar"), False)
        vbox.pack_start(self._uimanager.get_widget("/Toolbar"), False)        
        
        # sorting
        align = gtk.Alignment()
        align.set_padding(4, 0, 0, 0)
        vbox.pack_start(align, False)
        hbox = gtk.HBox(False, 12)
        align.add(hbox)
        hbox.pack_start(gtk.Label("Sort"), False)
        sorting_model = gtk.ListStore(*constants.SORTING_COLUMNS)
        sorting_model.append(("manually", constants.SORT_ID_MANUAL, None))
        
        for ii,sort in enumerate(collect.get_sort_from_modulename("sort")):
            inst = sort(self._files_model)
            sorting_model.append((inst.short_description, ii+1, inst))
            self._files_model.set_sort_func(ii+1, inst.sort)
        
        sorting_combobox = gtk.ComboBox(sorting_model)
        cell = gtk.CellRendererText()
        sorting_combobox.pack_start(cell, True)
        sorting_combobox.add_attribute(cell, "text", 0)
        sorting_combobox.set_active(0)
        hbox.pack_start(sorting_combobox, False)
        order_check = gtk.CheckButton("descending")
        order_check.set_sensitive(False)
        sort_config_container = gtk.HBox(False, 0)
        order_check.connect("toggled", sorting_order_check_toggled, self._files_model, sorting_combobox, sort_config_container)
        hbox.pack_start(order_check, False)
        hbox.pack_start(sort_config_container, True)
        sorting_combobox.connect("changed", sorting_combobox_changed, self._files_model, order_check, sort_config_container)

        # add file list widget from base class
        vbox.pack_start(self._file_list_widget)

        # hsep
        vbox.pack_start(gtk.HSeparator(), False, False, 4)
        
        # mode selection
        alignment = gtk.Alignment()
        alignment.set_padding(6, 0, 0, 0)
        vbox.pack_start(alignment, False)
        label = gtk.Label()
        label.set_markup("<b>Mode:</b>")
        alignment.add(label)

        # previews
        self._previews_model = self._collect_previews()
        filteredmodel = self._previews_model.filter_new()
        filteredmodel.set_visible_column(constants.PREVIEWS_COLUMN_VISIBLE)
        
        alignment = gtk.Alignment(xscale=1)
        alignment.set_padding(6, 0, 18, 0)
        vbox.pack_start(alignment, False)
        self._previews_combobox = gtk.ComboBox(filteredmodel)
        cell = gtk.CellRendererText()
        self._previews_combobox.pack_start(cell, True)
        self._previews_combobox.add_attribute(cell, "text", 0)
        self._previews_combobox.connect("changed", self._on_previews_combobox_changed)
        alignment.add(self._previews_combobox)

        # config area
        alignment = gtk.Alignment()
        alignment.set_padding(18, 0, 0, 0)
        vbox.pack_start(alignment, False)
        label = gtk.Label()
        label.set_markup("<b>Configuration:</b>")
        alignment.add(label)
        
        self._config_container = gtk.Alignment(xscale=1)
        self._config_container.set_padding(8, 0, 18, 0)
        vbox.pack_start(self._config_container, False)
        
        # hsep
        vbox.pack_start(gtk.HSeparator(), False, False, 4)

        # rename, cancel, and more buttons
        buttonbox = gtk.HButtonBox()
        buttonbox.set_layout(gtk.BUTTONBOX_END)
        buttonbox.set_spacing(12)
        vbox.pack_start(buttonbox, False)

        close_button = gtk.Button(stock=gtk.STOCK_CLOSE)
        close_button.connect("clicked", lambda button, self : self.quit(), self)
        buttonbox.add(close_button)

        buttonbox.add(self._rename_button)

        # prefs window
        self._preferences_window = preferences.Window(self._previews_model)

        # restore state
        self._restore_state()
        
        try:
            self._current_preview.grab_focus()
        except AttributeError:
            pass
        
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
        
        # previews combo box
        filtered_previews_model = self._previews_combobox.get_model()
        idx = self._previews_combobox.get_active()
        if idx >= 0:
            state["current_preview_short_description"] = filtered_previews_model[idx][0] 
            
        pickle.dump(state, open(os.path.join(config.config_dir, "state"), "w"))


    def _restore_state(self):
        # state restore
        statesavefilename = os.path.join(config.config_dir, "state")
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


    def _on_action_add(self, dummy=None):
        dlg = gtk.FileChooserDialog("Add..", self._window, gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dlg.set_default_response(gtk.RESPONSE_OK)
        dlg.set_select_multiple(True)
        response = dlg.run()
        uris = []
        if response == gtk.RESPONSE_OK:
            uris = dlg.get_uris()
        dlg.destroy()
        if uris:
            self._add_to_files_model(uris)


    def _on_action_add_folders(self, dummy=None):
        
        def add_folder_children(folder, uris, include_hidden):
            for fileinfo in folder.enumerate_children(",".join([gio.FILE_ATTRIBUTE_STANDARD_NAME, gio.FILE_ATTRIBUTE_STANDARD_TYPE, gio.FILE_ATTRIBUTE_STANDARD_IS_HIDDEN])):
                child = folder.get_child(fileinfo.get_name())
                if not include_hidden and fileinfo.get_is_hidden():
                    continue
                uris.append(child.get_uri())
                if fileinfo.get_file_type() == gio.FILE_TYPE_DIRECTORY:
                    add_folder_children(child, uris, include_hidden)
        
        dlg = gtk.FileChooserDialog("Add..", self._window, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dlg.set_default_response(gtk.RESPONSE_OK)
        dlg.set_select_multiple(True)
        vbox = gtk.VBox(False, 4)
        recursive_check = gtk.CheckButton("Select recursively")
        vbox.pack_start(recursive_check)
        include_hidden_folders_check = gtk.CheckButton("Include hidden files and folders")
        vbox.pack_start(include_hidden_folders_check)
        vbox.show_all()
        dlg.set_extra_widget(vbox)
        response = dlg.run()
        selected_uris = []
        uris = []
        include_hidden = include_hidden_folders_check.get_active() 
        if response == gtk.RESPONSE_OK:
            selected_uris = dlg.get_uris()
            for uri in selected_uris:
                file = gio.File(uri=uri)
                if not include_hidden and file.query_info(gio.FILE_ATTRIBUTE_STANDARD_IS_HIDDEN).get_is_hidden():
                    continue
                uris.append(uri)
                if recursive_check.get_active():
                    add_folder_children(file, uris, include_hidden)
                    
        dlg.destroy()
        if uris:
            self._add_to_files_model(uris)        

    def _on_action_remove(self, dummy=None):
        selection = self._files_treeview.get_selection()
        (model, selected) = selection.get_selected_rows()
        iters = [model.get_iter(path) for path in selected]
        for iter in iters:
            model.remove(iter)
        self.refresh(model_changed=True)


    def _on_action_clear(self, dummy=None):
        self._files_model.clear()
        self.refresh(model_changed=True)

    def _on_action_preferences(self, dummy=None):
        self._preferences_window.show()

    def _on_action_quit(self, dummy=None):
        self.quit()

    def _on_delete_event(self, widget, event):
        self.quit()
        return True

    def _on_action_about(self, dummy=None):
        """Credits dialog"""
        authors = ["Holger Berndt <hb@gnome.org>"]
        about = gtk.AboutDialog()
        about.set_version("v%s" % constants.__version__)
        about.set_authors(authors)
        about.set_license("GNU Lesser General Public License v2.1")
        about.set_transient_for(self._window)
        about.connect("response", lambda dlg, unused: dlg.destroy())
        about.show()


    def _on_previews_combobox_changed(self, combobox):
        previewclass = combobox.get_model()[combobox.get_active()][constants.PREVIEWS_COLUMN_PREVIEW]
        self._current_preview = previewclass(self.refresh, self._files_model)

        # configuration
        child = self._config_container.get_child()
        if child:
            self._config_container.remove(child)
        try:
            config_widget = self._current_preview.get_config_widget()
        except AttributeError:
            config_widget = gtk.Alignment()
            config_widget.add(gtk.Label("This mode doesn't have any configuration options."))
        self._config_container.add(config_widget)
        self._config_container.show_all()

        # refresh
        self.refresh()


    def _collect_previews(self):
        """Fill combobox with previews"""
        # builtin
        previews_model = collect.get_previews_from_modulname("preview")

        # user specific
        if not os.path.isdir(config.user_previewers_dir):
            try:
                os.makedirs(config.user_previewers_dir)
            except OSError:
                self._logger.debug("Could not create '%s'" % config.user_previewers_dir)
            else:
                self._logger.debug("Created '%s'" % config.user_previewers_dir)
        try:
            files = os.listdir(config.user_previewers_dir)
        except OSError:
            self._logger.warning("Could not list '%s'" % config.user_previewers_dir)
        else:
            modules = set()
            for file in files:
                if file.endswith(".py"):
                    modules.add(file[0:-3])
                elif file.endswith(".pyc"):
                    modules.add(file[0:-4])

            sys.path.insert(0, config.user_previewers_dir)
            for modulname in modules:
                collect.get_previews_from_modulname(modulname, previews_model)
            del sys.path[0]
    
        previews_model.set_default_sort_func(lambda model, iter1, iter2 : cmp(model.get_value(iter1, constants.PREVIEWS_COLUMN_PRIORITY), model.get_value(iter2, constants.PREVIEWS_COLUMN_PRIORITY)))
        previews_model.set_sort_column_id(gtk.TREE_SORTABLE_DEFAULT_SORT_COLUMN_ID, gtk.SORT_ASCENDING)
        return previews_model
    
