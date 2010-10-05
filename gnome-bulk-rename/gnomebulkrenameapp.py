# GNOME bulk rename utility
# Copyright (C) 2010 Holger Berndt <hb@gnome.org>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

import cPickle as pickle
import sys # only debug

import os
import os.path
import urllib
import logging
import logging.handlers
import subprocess

import pygtk
pygtk.require("2.0")
from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

from gettext import gettext as _

from preview import PreviewNoop,PreviewReplaceLongestSubstring, PreviewCommonModificationsSimple
from markup import MarkupColor
from sort import Manually as SortManually
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
        self._file_list_widget = Gtk.VBox.new(False, 0)

        # rename button widget
        self._rename_button = Gtk.Button(label=_("Rename"))
        self._rename_button.connect("clicked", self._on_rename_button_clicked)

        # info bar
        self._files_info_bar = Gtk.InfoBar()
        self._files_info_bar.connect("response", self._on_files_info_bar_response)
        self._files_info_bar.set_no_show_all(True)
        self._file_list_widget.pack_start(self._files_info_bar, False, True, 0)

        # filename list
        scrolledwin = Gtk.ScrolledWindow()
        scrolledwin.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolledwin.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self._file_list_widget.pack_start(scrolledwin, True, True, 4)
        self._files_model = Gtk.ListStore(*constants.FILES_MODEL_COLUMNS)
        self._files_model.connect("row-deleted", files_model_row_deleted_cb, self)
        treeview = Gtk.TreeView(model=self._files_model)
        treeview.set_size_request(450, 100)
        row_targets = [('text/uri-list', Gtk.TargetFlags.OTHER_APP, GnomeBulkRenameAppBase.TARGET_TYPE_URI_LIST),
                        ("GTK_TREE_MODEL_ROW", Gtk.TargetFlags.SAME_WIDGET, GnomeBulkRenameAppBase.TARGET_TYPE_MODEL_ROW)]
#HHBTODO        treeview.enable_model_drag_source(Gdk.ModifierType.BUTTON1_MASK, row_targets, len(row_targets), Gdk.DragAction.MOVE)
#HHBTODO        treeview.enable_model_drag_dest(row_targets, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        treeview.connect("drag-data-received", self._on_drag_data_received)
        selection = treeview.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        selection.connect("changed", self._on_tree_selection_changed)
        textrenderer = Gtk.CellRendererText()
        pixbufrenderer = Gtk.CellRendererPixbuf()
        # column icon
        column = Gtk.TreeViewColumn("", pixbufrenderer, stock_id=constants.FILES_MODEL_COLUMN_ICON_STOCK)
        column.set_expand(False)
        treeview.append_column(column)
        # column "original"
        column = Gtk.TreeViewColumn("original", textrenderer, markup=constants.FILES_MODEL_COLUMN_MARKUP_ORIGINAL)
        column.set_expand(True)
        treeview.append_column(column)
        # column "preview"
        column = Gtk.TreeViewColumn("preview", textrenderer, markup=constants.FILES_MODEL_COLUMN_MARKUP_PREVIEW)
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



    def refresh(self, did_just_rename=False, model_changed=False, name_part_restriction_changed=False):
        """Re-calculate previews"""
        
        if did_just_rename:
            try:
                self._current_preview.post_rename(self._files_model)
            except AttributeError:
                pass

        # possibly restrict to file name part
        try:
            active = self._restrict_to_name_part_combo.get_active()
        except AttributeError:
            active = 0

        # when full filename is used, we can use the file model directly
        if active == 0:
            model = self._files_model
        else:
            model = []
            for row in self._files_model:
                (root, ext) = os.path.splitext(row[0])
                if active == 1:
                    model.append([root, root, ext])
                else:
                    if len(ext) > 0:
                        dot = "."
                    else:
                        dot = ""
                    model.append([ext[1:], ext[1:], root, dot])
        
        if name_part_restriction_changed or model_changed:
            try:
                self._current_preview.model_changed(model)
            except AttributeError:
                pass

        # preview if valid
        try:
            valid = self._current_preview.valid
        except AttributeError:
            valid = True
        
        if valid:
            try:
                self._current_preview.preview(model)
            except Exception, ee:
                valid = False
            else:
                # if necessary, write back results
                if active == 1:
                    for ii,row in enumerate(model):
                        self._files_model[ii][1] = row[1]+row[2]
                elif active == 2:
                    for ii,row in enumerate(model):
                        self._files_model[ii][1] = row[2]+row[3]+row[1]
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
        else:
            self._set_info_bar_according_to_problem_level(0)

    def _on_tree_selection_changed(self, selection):
        # removing does not exist in simple mode
        try:
            self._remove_action.set_sensitive(selection.count_selected_rows() > 0)
        except AttributeError:
            pass

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
                        if entry.startswith("<b>%s" % _("ERROR")) or entry.startswith("<b>%s" % _("WARNING")):
                            problems.add(entry)
            if problems:
                if response_id == constants.FILES_INFO_BAR_RESPONSE_ID_INFO_WARNING:
                    dlg_type = Gtk.MessageType.WARNING
                    msg = _("The following problems might prevent renaming:")
                else:
                     dlg_type = Gtk.MessageType.ERROR
                     msg = _("The following problems prevent renaming:") 
                dlg = Gtk.MessageDialog(parent=self._window, type=dlg_type, buttons=Gtk.ButtonsType.CLOSE, message_format=msg)
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
        gfiles = [Gio.file_new_for_uri(uri) for uri in uris]
        # make sure they don't refer to identical uris (back and forth for normalization inside GFile)
        uris = set()
        for gfile in gfiles:
            uris.add(gfile.get_uri())
        gfiles = [Gio.file_new_for_uri(uri) for uri in uris]
        
        files_to_add = []
        for gfile in gfiles:
            # checking for already existing files
            if self._is_file_in_model(gfile):
                continue
            fileinfo = gfile.query_info(Gio.FILE_ATTRIBUTE_STANDARD_EDIT_NAME, Gio.FileQueryInfoFlags.NONE, None)
            if fileinfo:
                filename = fileinfo.get_attribute_as_string(Gio.FILE_ATTRIBUTE_STANDARD_EDIT_NAME)
                try:
                    dirname = __get_uri_dirname(gfile)
                except ValueError:
                    self._logger.error("Cannot add URI because it contains no slash: '%s'" % gfile.get_uri())
                    continue
                files_to_add.append([filename, "", "", "", gfile, "", "", dirname])

        # add to model
        for file in files_to_add:
            self._files_model.append(file)
        self.refresh(model_changed=True)


    def _is_file_in_model(self, gfile):
        """Return True if the given Gio.File is already in the files model, False otherwise"""
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

        hbox = Gtk.HBox.new(False, 4)
        
        if highest_level == 1:
            hbox.pack_start(Gtk.Image.new_from_stock(Gtk.STOCK_DIALOG_WARNING, Gtk.IconSize.LARGE_TOOLBAR), True, True, 0)
            hbox.pack_start(Gtk.Label(label=_("Expect problems when trying to rename")), True, True, 0)
            hbox.show_all()
            content_area.pack_start(hbox, False, True, 0)
            self._files_info_bar.set_message_type(Gtk.MessageType.WARNING)
            self._files_info_bar.add_button(Gtk.STOCK_INFO, constants.FILES_INFO_BAR_RESPONSE_ID_INFO_WARNING)
            self._files_info_bar.show()
            
        elif highest_level == 2:
            hbox.pack_start(Gtk.Image.new_from_stock(Gtk.STOCK_DIALOG_ERROR, Gtk.IconSize.LARGE_TOOLBAR), True, True, 0)
            hbox.pack_start(Gtk.Label(label=_("Rename not possible")), True, True, 0)
            hbox.show_all()
            content_area = self._files_info_bar.get_content_area()
            gtkutils.clear_gtk_container(content_area)
            content_area.pack_start(hbox, False, True, 0)
            self._files_info_bar.set_message_type(Gtk.MessageType.ERROR)
            self._files_info_bar.add_button(Gtk.STOCK_INFO, constants.FILES_INFO_BAR_RESPONSE_ID_INFO_ERROR)
            self._files_info_bar.show()


    def _set_info_bar_according_to_rename_operation(self, num_renames, num_errors, was_undo):

        content_area = self._files_info_bar.get_content_area()
        gtkutils.clear_gtk_container(content_area)
        action_area = self._files_info_bar.get_action_area()
        gtkutils.clear_gtk_container(action_area)
        
        hbox = Gtk.HBox.new(False, 4)
        
        if num_errors > 0:
            hbox.pack_start(Gtk.Image.new_from_stock(Gtk.STOCK_DIALOG_WARNING, Gtk.IconSize.LARGE_TOOLBAR), False, True, 0)
            self._files_info_bar.set_message_type(Gtk.MessageType.WARNING)
            if not was_undo:
                hbox.pack_start(Gtk.Label(label=_("Problems occured during rename")), False, True, 0)
            else:
                hbox.pack_start(Gtk.Label(label=_("Problems occured during undo")), False, True, 0)
        else:
            self._files_info_bar.set_message_type(Gtk.MessageType.INFO)
            if not was_undo:
                hbox.pack_start(Gtk.Label(label=_("Files successfully renamed")), False, True, 0)
            else:
                hbox.pack_start(Gtk.Label(label=_("Undo successful")), False, True, 0)
        
        hbox.show_all()
        content_area.pack_start(hbox, False, True, 0)
        
        # undo button
        if num_renames > 0:
            if not was_undo:
                button = Gtk.Button(stock=Gtk.STOCK_UNDO)
                button.connect("clicked", self._on_undo_button_clicked)
            else:
                button = Gtk.Button(stock=Gtk.STOCK_REDO)
                button.connect("clicked", self._on_redo_button_clicked)
            button.show()
            action_area.pack_start(button, True, True, 0)
                
        
        self._files_info_bar.show()        


    def _update_files_model_tooltips_column(self):
        for row in self._files_model:
            tooltips = row[constants.FILES_MODEL_COLUMN_TOOLTIP].split()
            if tooltips:
                del tooltips[0]
            else:
                tooltips = [] 
            tooltips.insert(0, row[constants.FILES_MODEL_COLUMN_GFILE].get_uri())
            row[constants.FILES_MODEL_COLUMN_TOOLTIP] = "\n".join(tooltips)


    def _on_rename_completed(self, results):
        self._logger.debug("Rename completed")
        self._update_files_model_tooltips_column()
        undo_action = rename.RenameUndoAction(results)
        undo_action.set_done_callback(self._on_undo_rename_completed)
        self._undo.push(undo_action)
        self.refresh(did_just_rename=True)
        self._set_info_bar_according_to_rename_operation(len(results.rename_data), len(results.errors), False)
        # TODO throttle off
        
                    
    def _on_undo_rename_completed(self, results, undo_action):
        self._logger.debug("Undo rename done")
        self._update_files_model_tooltips_column()
        if len(results.rename_data) > 0:
            undo_action.set_done_callback(self._on_redo_rename_completed)
            self._undo.push_to_redo(undo_action)
        self.refresh(did_just_rename=True)
        self._set_info_bar_according_to_rename_operation(len(results.rename_data), len(results.errors), True)
        

    def _on_redo_rename_completed(self, results, undo_action):
        self._logger.debug("Redo rename done")
        self._update_files_model_tooltips_column()
        if len(results.rename_data) > 0:
            undo_action.set_done_callback(self._on_undo_rename_completed)
            self._undo.push_back_to_undo(undo_action)
        self.refresh(did_just_rename=True)
        self._set_info_bar_according_to_rename_operation(len(results.rename_data), len(results.errors), False)


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

        GLib.set_application_name(config.appname + "-simple")

        self._logger = logging.getLogger("gnome.bulk-rename.bulk-rename-simple")
        self._logger.debug("init")

        # window
        self._window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self._window.set_title(_("Bulk Rename"))
        self._window.set_border_width(4)
        self._window.connect("destroy", lambda o : Gtk.main_quit())
        self._window.connect("delete-event", self._on_delete_event)

        # main vbox
        vbox = Gtk.VBox.new(False, 0)
        self._window.add(vbox)

        # description
        hbox = Gtk.HBox.new(False, 0)
        hbox.pack_start(Gtk.Image.new_from_stock(Gtk.STOCK_DIALOG_INFO, Gtk.IconSize.DIALOG), False, True, 0)
        hbox.pack_start(Gtk.Label(label=_("You can choose among some common rename operations,\nor press the 'Advanced' button for more options.")), False, True, 0)
        vbox.pack_start(hbox, False, True, 0)

        # add file list
        vbox.pack_start(self._file_list_widget, True, True, 0)

        # hsep
        vbox.pack_start(Gtk.HSeparator(), False, False, 4)

        # create previewer, and add config
        # first, try "longest common substring"
        self._current_preview = PreviewReplaceLongestSubstring(self.refresh, self._files_model)
        # if that doesn't work, offer some common simple modifications
        if not self._current_preview.valid:
            self._logger.debug("URIs don't have a common substring, offer simple modifications instead.")
            self._current_preview = PreviewCommonModificationsSimple(self.refresh, self._files_model)
        self.refresh()
        
        vbox.pack_start(self._current_preview.get_config_widget(), False, True, 0)
        
        # hsep
        vbox.pack_start(Gtk.HSeparator(), False, False, 4)
        
        # rename, cancel, and more buttons
        buttonbox = Gtk.HButtonBox()
        buttonbox.set_layout(Gtk.ButtonBoxStyle.END)
        buttonbox.set_spacing(12)
        vbox.pack_start(buttonbox, False, True, 0)

        advanced_button = Gtk.Button(label=_("Advanced"))
        advanced_button.connect("clicked", self._on_advanced_button_clicked)
        buttonbox.add(advanced_button)

        close_button = Gtk.Button(stock=Gtk.STOCK_CLOSE)
        close_button.connect("clicked", lambda button, self : self.quit(), self)
        buttonbox.add(close_button)        

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
        cmd.insert(0, "/home/hb/src/gnome-bulk-rename/gnome-bulk-rename/gnome-bulk-rename.py") # TODO
        try:
            subprocess.Popen(cmd)
        except OSError, ee:
            self._logger.error("Command invokation failed: '%s'" % "".join(cmd))
            # open an error dialog
            dlg = Gtk.MessageDialog(self._window, Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE)
            dlg.set_title(_("Switch failed"))
            dlg.set_markup("<b>%s</b>" % _("Switch to advanced mode failed"))
            dlg.format_secondary_markup(_("The command '%s' could not be found.") % cmd[0])
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

            gtkutils.clear_gtk_container(config_container)

            idx = combobox.get_active()
            if idx == -1:
                files_model.set_sort_column_id(constants.SORT_ID_MANUAL, Gtk.SortType.ASCENDING)
                return

            instance = combobox.get_model()[idx][constants.EXTENSIBLE_MODEL_COLUMN_OBJECT]
            if not hasattr(instance, "short_description"):
                sort_id = constants.SORT_ID_MANUAL
            else:
                sort_id = instance.sort_id
            if order_check.get_active():
                order = Gtk.SortType.DESCENDING
            else:
                order = Gtk.SortType.ASCENDING

            if sort_id == constants.SORT_ID_MANUAL:
                order_check.set_sensitive(False)
#HHBTODO Gtk.TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID auf -2 gesetzt
                files_model.set_sort_column_id(-2, order)
            else:
                order_check.set_sensitive(True)
                if hasattr(inst, "get_config_widget"):
                    config_container.pack_start(inst.get_config_widget(), False, True, 0)
                    config_container.show_all()
                files_model.set_sort_column_id(sort_id, order)


        def sorting_order_check_toggled(checkbutton, model, combobox, config_container):
            sorting_combobox_changed(combobox, model, checkbutton, config_container)

        def markup_toggled(new_row_num):
            self._current_markup = self._markups_model[new_row_num][constants.EXTENSIBLE_MODEL_COLUMN_OBJECT]()
            self.refresh()

        # application name
        GLib.set_application_name(config.appname)

        self._logger = logging.getLogger("gnome.bulk-rename.bulk-rename")
        self._logger.debug("init")
        
        # actions
        self._uimanager = Gtk.UIManager()
        self._action_group = Gtk.ActionGroup(name = "mainwindow")
        actions = [("file", None, "_File"),
                   ("edit", None, "_Edit"),
                   ("view", None, "_View"),
                   ("add", Gtk.STOCK_ADD, _("Add files ..."), None, _("Add files to the list"), self._on_action_add),
                   ("addfolders", None, _("Add folders ..."), None, _("Add folders to the list"), self._on_action_add_folders),
                   ("remove", Gtk.STOCK_REMOVE, _("Remove files"), None, _("Remove selected files from the list"), self._on_action_remove),
                   ("clear", Gtk.STOCK_CLEAR, _("Clear"), None, _("Removes all files from the list"), self._on_action_clear),
                   ("preferences", Gtk.STOCK_PREFERENCES, _("Preferences"), None, _("Preferences"), self._on_action_preferences),
                   ("quit", Gtk.STOCK_QUIT, _("_Quit"), "<Control>q", _("Quit the Program"), self._on_action_quit),
                   ("help", None, _("_Help")),
                   ("about", Gtk.STOCK_ABOUT, _("About"), None, _("About this program"), self._on_action_about)
                   ]
        self._action_group.add_actions(actions)
        self._action_group.add_action(self._undo.get_undo_action())
        self._action_group.add_action(self._undo.get_redo_action())
        self._uimanager.insert_action_group(self._action_group, -1)
        self._uimanager.add_ui_from_string(self.__ui)
        self._remove_action = self._action_group.get_action("remove")
        self._remove_action.set_sensitive(False)

        # window
        self._window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self._window.set_title(_("Bulk Rename"))
        self._window.set_size_request(450, 600)
        self._window.set_border_width(4)
        self._window.connect("destroy", lambda o : Gtk.main_quit())
        self._window.connect("delete-event", self._on_delete_event)
        self._window.add_accel_group(self._uimanager.get_accel_group())
        
        vbox = Gtk.VBox.new(False, 0)
        self._window.add(vbox)

        # menu bar
        vbox.pack_start(self._uimanager.get_widget("/Menubar"), False, True, 0)
        vbox.pack_start(self._uimanager.get_widget("/Toolbar"), False, True, 0)
        
        # sorting
        align = Gtk.Alignment(xalign=0.0, yalign=0.0, xscale=0.0, yscale=0.0)
        align.set_padding(4, 0, 0, 0)
        vbox.pack_start(align, False, True, 0)
        hbox = Gtk.HBox.new(False, 12)
        align.add(hbox)
        hbox.pack_start(Gtk.Label(label = _("Sort")), False, True, 0)

        self._sorting_model = collect.get_extensible_model("sort", ["sort"])
        for ii,row in enumerate(self._sorting_model):
            # replace class object by actual instances
            inst = row[constants.EXTENSIBLE_MODEL_COLUMN_OBJECT](self._files_model)
            inst.sort_id = ii+1
            self._sorting_model[ii][constants.EXTENSIBLE_MODEL_COLUMN_OBJECT] = inst
            self._files_model.set_sort_func(inst.sort_id, inst.sort, None)
        # insert "manually" as first element
        self._sorting_model.insert(0, (_("manually"), SortManually(), 0., True, _("manually")))        

        filteredmodel = self._sorting_model.filter_new(None)
        filteredmodel.set_visible_column(constants.EXTENSIBLE_MODEL_COLUMN_VISIBLE)
        
        sorting_combobox = Gtk.ComboBox(model=filteredmodel)
        cell = Gtk.CellRendererText()
        sorting_combobox.pack_start(cell, True)
        sorting_combobox.add_attribute(cell, "text", 0)
        hbox.pack_start(sorting_combobox, False, True, 0)
        order_check = Gtk.CheckButton(label=_("descending"))
        order_check.set_sensitive(False)
        sort_config_container = Gtk.HBox.new(False, 0)
        order_check.connect("toggled", sorting_order_check_toggled, self._files_model, sorting_combobox, sort_config_container)
        hbox.pack_start(order_check, False, True, 0)
        hbox.pack_start(sort_config_container, True, True, 0)
        sorting_combobox.connect("changed", sorting_combobox_changed, self._files_model, order_check, sort_config_container)
        sorting_combobox.set_active(0)

        # add file list widget from base class
        vbox.pack_start(self._file_list_widget, True, True, 0)

        # hsep
        vbox.pack_start(Gtk.HSeparator(), False, False, 4)

        # restrictions
        alignment = Gtk.Alignment(xalign=0.0, yalign=0.0, xscale=0.0, yscale=0.0)
        alignment.set_padding(6, 0, 0, 0)
        vbox.pack_start(alignment, False, True, 0)
        label = Gtk.Label()
        label.set_markup("<b>%s:</b>" % "Restrictions")
        alignment.add(label)

        # combo box files / only extension / filename without extension
        alignment = Gtk.Alignment(xalign=0.0, yalign=0.0, xscale=1.0, yscale=0.0)
        alignment.set_padding(6, 0, 18, 0)
        vbox.pack_start(alignment, False, True, 0)

        hbox = Gtk.HBox.new(False, 12)
        alignment.add(hbox)

        hbox.pack_start(Gtk.Label(label = _("Name parts:")), False, True, 0)

        combobox = Gtk.ComboBoxText.new()
        combobox.append_text(_("Whole filename"))
        combobox.append_text(_("Filename without extension"))
        combobox.append_text(_("Extension only"))
        combobox.set_active(0)
        hbox.pack_start(combobox, True, True, 0)
        self._restrict_to_name_part_combo = combobox
        self._restrict_to_name_part_combo.connect("changed", lambda combo, self : self.refresh(name_part_restriction_changed=True), self)
        
        # hsep
        vbox.pack_start(Gtk.HSeparator(), False, False, 4)

        # mode selection
        alignment = Gtk.Alignment(xalign=0.0, yalign=0.0, xscale=0.0, yscale=0.0)
        alignment.set_padding(6, 0, 0, 0)
        vbox.pack_start(alignment, False, True, 0)
        label = Gtk.Label()
        label.set_markup("<b>%s:</b>" % "Mode")
        alignment.add(label)

        # previews
        self._previews_model = collect.get_extensible_model("preview", ["preview"])
        filteredmodel = self._previews_model.filter_new(None)
        filteredmodel.set_visible_column(constants.EXTENSIBLE_MODEL_COLUMN_VISIBLE)
 
        alignment = Gtk.Alignment(xalign=0.0, yalign=0.0, xscale=1.0, yscale=0.0)
        alignment.set_padding(6, 0, 18, 0)
        vbox.pack_start(alignment, False, True, 0)
        self._previews_combobox = Gtk.ComboBox(model=filteredmodel)
        cell = Gtk.CellRendererText()
        self._previews_combobox.pack_start(cell, True)
        self._previews_combobox.add_attribute(cell, "text", 0)
        self._previews_combobox.connect("changed", self._on_previews_combobox_changed)
        alignment.add(self._previews_combobox)

        # markup
        self._markups_model = collect.get_extensible_model("markup", ["markup"])
        for row in self._markups_model:
            try:
                if row[constants.EXTENSIBLE_MODEL_COLUMN_OBJECT].default:
                    row[constants.EXTENSIBLE_MODEL_COLUMN_VISIBLE] = True
                else:
                    row[constants.EXTENSIBLE_MODEL_COLUMN_VISIBLE] = False
            except AttributeError:
                row[constants.EXTENSIBLE_MODEL_COLUMN_VISIBLE] = False
            
        filteredmodel = self._markups_model.filter_new(None)
        filteredmodel.set_visible_column(constants.EXTENSIBLE_MODEL_COLUMN_VISIBLE)

        # config area
        alignment = Gtk.Alignment(xalign=0.0, yalign=0.0, xscale=0.0, yscale=0.0)
        alignment.set_padding(18, 0, 0, 0)
        vbox.pack_start(alignment, False, True, 0)
        label = Gtk.Label()
        label.set_markup("<b>%s:</b>" % "Configuration")
        alignment.add(label)
        
        self._config_container = Gtk.Alignment(xalign=0.0, yalign=0.0, xscale=1.0, yscale=0.0)
        self._config_container.set_padding(8, 0, 18, 0)
        vbox.pack_start(self._config_container, False, True, 0)
        
        # hsep
        vbox.pack_start(Gtk.HSeparator(), False, False, 4)

        # rename, cancel, and more buttons
        buttonbox = Gtk.HButtonBox()
        buttonbox.set_layout(Gtk.ButtonBoxStyle.END)
        buttonbox.set_spacing(12)
        vbox.pack_start(buttonbox, False, True, 0)

        close_button = Gtk.Button(stock=Gtk.STOCK_CLOSE)
        close_button.connect("clicked", lambda button, self : self.quit(), self)
        buttonbox.add(close_button)

        buttonbox.add(self._rename_button)

        # prefs window
        self._preferences_window = preferences.Window(self._previews_model, self._sorting_model, self._markups_model, markup_toggled)

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
        
        def save_extensible_model(model, name):
            visibility_entries = {}
            key = "item_visibility_" + name
            for row in model:
                visibility_entries[row[constants.EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION]] = row[constants.EXTENSIBLE_MODEL_COLUMN_VISIBLE]
            state[key] = visibility_entries
        
        self._logger.debug("Saving state")
        state = {}
        
        # previews combo box
        filtered_previews_model = self._previews_combobox.get_model()
        idx = self._previews_combobox.get_active()
        if idx >= 0:
            state["current_preview_short_description"] = filtered_previews_model[idx][0] 
        
        # extensible models
        save_extensible_model(self._previews_model, "preview")
        save_extensible_model(self._sorting_model, "sorting")
 
        # restrict to name part combo
        state["restrict_to_name_part_combo"] = self._restrict_to_name_part_combo.get_active() 

        # markup
        for row in self._markups_model:
            if row[constants.EXTENSIBLE_MODEL_COLUMN_VISIBLE]:
                state["current_markup"] = row[constants.EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION]
        
        pickle.dump(state, open(os.path.join(config.config_dir, "state"), "w"))


    def _restore_state(self):
        
        def restore_extensible_model(model, name):
            key = "item_visibility_" + name 
            if key in state:
                visibility_entries = state[key]
                for row in model:
                    if row[constants.EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION] in visibility_entries:
                        row[constants.EXTENSIBLE_MODEL_COLUMN_VISIBLE] = visibility_entries[row[constants.EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION]]
                        if row[constants.EXTENSIBLE_MODEL_COLUMN_VISIBLE]:
                            row[constants.EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION_MARKUP] = row[constants.EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION]
                        else:
                            row[constants.EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION_MARKUP] = "".join(['<span color="gray">', row[constants.EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION], '</span>'])  

        # state restore
        statesavefilename = os.path.join(config.config_dir, "state")
        if not os.path.isfile(statesavefilename):
            return
        
        self._logger.debug("Restoring state")
        state = pickle.load(open(statesavefilename, "r"))

        # extensible models
        restore_extensible_model(self._sorting_model, "sorting")
        restore_extensible_model(self._previews_model, "preview")

        # markup
        row_num = None
        if "current_markup" in state:
            for irow, row in enumerate(self._markups_model):
                if row[constants.EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION] == state["current_markup"]:
                    row_num = irow
                    self._current_markup = row[constants.EXTENSIBLE_MODEL_COLUMN_OBJECT]()
                    break
        if row_num is not None:
            for irow, row in enumerate(self._markups_model):
                row[constants.EXTENSIBLE_MODEL_COLUMN_VISIBLE] = (irow == row_num)
                
        # previews combo box
        tar = 0 
        if "current_preview_short_description" in state:
            desc = state["current_preview_short_description"]
            for ii, row in enumerate(self._previews_combobox.get_model()):
                if row[0] == desc:
                    tar = ii
                    break
        self._previews_combobox.set_active(tar)
        
        # restrict to name part combo
        if "restrict_to_name_part_combo" in state:
            self._restrict_to_name_part_combo.set_active(state["restrict_to_name_part_combo"])


    def _on_action_add(self, action, user_data=None):
        dlg = Gtk.FileChooserDialog(_("Add ..."), self._window, Gtk.FileChooserAction.OPEN, (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dlg.set_default_response(Gtk.ResponseType.OK)
        dlg.set_select_multiple(True)
        response = dlg.run()
        uris = []
        if response == Gtk.ResponseType.OK:
            uris = dlg.get_uris()
        dlg.destroy()
        if uris:
            self._add_to_files_model(uris)


    def _on_action_add_folders(self, action, user_data=None):
        
        def add_folder_children(folder, uris, include_hidden):
            root = Gio.file_new_for_uri("file:///")
            for fileinfo in root.enumerate_children(Gio.FILE_ATTRIBUTE_STANDARD_NAME, 0, None):                
#HHBTODO
                print fileinfo.get_name()
            
            
#HHBTODO: bug 634636
            for fileinfo in folder.enumerate_children(",".join([Gio.FILE_ATTRIBUTE_STANDARD_NAME, Gio.FILE_ATTRIBUTE_STANDARD_TYPE, Gio.FILE_ATTRIBUTE_STANDARD_IS_HIDDEN]), 0, None):
                child = folder.get_child(fileinfo.get_name())
                if not include_hidden and fileinfo.get_is_hidden():
                    continue
                uris.append(child.get_uri())
                if fileinfo.get_file_type() == Gio.FILE_TYPE_DIRECTORY:
                    add_folder_children(child, uris, include_hidden)
        
        dlg = Gtk.FileChooserDialog(_("Add ..."), self._window, Gtk.FileChooserAction.SELECT_FOLDER, (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dlg.set_default_response(Gtk.ResponseType.OK)
        dlg.set_select_multiple(True)
        vbox = Gtk.VBox.new(False, 4)
        recursive_check = Gtk.CheckButton(label=_("Select recursively"))
        vbox.pack_start(recursive_check, True, True, 0)
        include_hidden_folders_check = Gtk.CheckButton(label=_("Include hidden files and folders"))
        vbox.pack_start(include_hidden_folders_check, True, True, 0)
        vbox.show_all()
        dlg.set_extra_widget(vbox)
        response = dlg.run()
        selected_uris = []
        uris = []
        include_hidden = include_hidden_folders_check.get_active() 
        if response == Gtk.ResponseType.OK:
            selected_uris = dlg.get_uris()
            for uri in selected_uris:
                file = Gio.file_new_for_uri(uri)
                if not include_hidden and file.query_info(Gio.FILE_ATTRIBUTE_STANDARD_IS_HIDDEN, Gio.FileQueryInfoFlags.NONE, None).get_is_hidden():
                    continue
                uris.append(uri)
                if recursive_check.get_active():
                    add_folder_children(file, uris, include_hidden)
                    
        dlg.destroy()
        if uris:
            self._add_to_files_model(uris)        

    def _on_action_remove(self, action, user_data=None):
        selection = self._files_treeview.get_selection()
        (model, selected) = selection.get_selected_rows()
        iters = [model.get_iter(path) for path in selected]
        for iter in iters:
            model.remove(iter)
        self.refresh(model_changed=True)


    def _on_action_clear(self, action, user_data=None):
        self._files_model.clear()
        self.refresh(model_changed=True)

    def _on_action_preferences(self, action, user_data=None):
        self._preferences_window.show()

    def _on_action_quit(self, action, user_data=None):
        self.quit()

    def _on_delete_event(self, widget, event):
        self.quit()
        return True

    def _on_action_about(self, action, dummy=None):
        """Credits dialog"""
        authors = ["Holger Berndt <hb@gnome.org>"]
        about = Gtk.AboutDialog()
        about.set_version("v%s" % config.version)
        about.set_authors(authors)
        about.set_license(config.copying)
        about.set_transient_for(self._window)
        about.connect("response", lambda dlg, unused: dlg.destroy())
        about.show()


    def _on_previews_combobox_changed(self, combobox):
        # clean up
        child = self._config_container.get_child()
        if child:
            self._config_container.remove(child)

        # new setting
        idx = combobox.get_active()
        if idx == -1:
            self._current_preview = PreviewNoop(self.refresh, self._files_model)
            if len(combobox.get_model()) == 0:
                config_widget = Gtk.Alignment(xalign=0.0, yalign=0.0, xscale=0.0, yscale=0.0)
                config_widget.add(Gtk.Label(label=_("You don't have any previewers active.\nPlease check your preferences.")));
                self._config_container.add(config_widget)
                self._config_container.show_all()
        else:
            previewclass = combobox.get_model()[idx][constants.EXTENSIBLE_MODEL_COLUMN_OBJECT]
            self._current_preview = previewclass(self.refresh, self._files_model)

            # configuration
            try:
                config_widget = self._current_preview.get_config_widget()
            except AttributeError:
                config_widget = Gtk.Alignment(xalign=0.0, yalign=0.0, xscale=0.0, yscale=0.0)
                config_widget.add(Gtk.Label(label=_("This mode doesn't have any configuration options.")))
            self._config_container.add(config_widget)
            self._config_container.show_all()

        # refresh
        self.refresh()
