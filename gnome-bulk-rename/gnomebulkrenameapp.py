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


#TODO base class logger?

class GnomeBulkRenameAppBase(object):
    """Base class for bulk renamer frontends"""

    TARGET_TYPE_URI_LIST = 94

    def __init__(self, uris=None):

        # undo stack
        self._undo = undo.Undo()

        # set up filename list widget with infobar
        # subclasses can pack this where they want
        self._file_list_widget = gtk.VBox(False, 0)

        # filename list
        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        self._file_list_widget.pack_start(frame, True, True, 4)
        scrolledwin = gtk.ScrolledWindow()
        scrolledwin.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        frame.add(scrolledwin)
        self._files_model = gtk.ListStore(*constants.FILES_MODEL_COLUMNS)
        treeview = gtk.TreeView(self._files_model)
        treeview.set_size_request(450, 100)
        treeview.drag_dest_set(gtk.DEST_DEFAULT_MOTION | gtk.DEST_DEFAULT_HIGHLIGHT | gtk.DEST_DEFAULT_DROP,
                  [('text/uri-list', 0, GnomeBulkRenameAppBase.TARGET_TYPE_URI_LIST)], gtk.gdk.ACTION_COPY)
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
        self._files_info_bar.connect("response", self._on_files_info_bar_response)
        self._files_info_bar.set_no_show_all(True)
        self._file_list_widget.pack_start(self._files_info_bar, False)

        # rename button widget
        self._rename_button = gtk.Button()
        button_hbox = gtk.HBox(False, 2)
        button_hbox.pack_start(gtk.image_new_from_stock(gtk.STOCK_CONVERT, gtk.ICON_SIZE_BUTTON))
        button_hbox.pack_start(gtk.Label("Rename"))
        self._rename_button.add(button_hbox)
        self._rename_button.connect("clicked", self._on_rename_button_clicked)

        # current preview and markup
        self._current_preview = PreviewNoop(self.refresh, self.preview_invalid, self._files_model)
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
            self._current_preview.preview(self._files_model)
        else:
            for row in self._files_model:
                row[1] = row[0]
                
        # markup
        self._current_markup.markup(self._files_model)
        
        if not did_just_rename:
            self._checker = check.Checker(self._files_model)
            self._checker.perform_checks()
            self._update_rename_button_sensitivity()
            self._set_info_bar_according_to_problem_level(self._checker.highest_problem_level)


    def preview_invalid(self):
        self._rename_button.set_sensitive(False)


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


    def _on_rename_completed(self, num_renames, num_errors, undo_action):
        self._logger.debug("Rename completed")
        
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
            self._undo.push(undo_action)
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
        self._window.set_title("Bulk Rename")
        self._window.set_border_width(5)
        self._window.connect("destroy", gtk.main_quit)
        self._window.connect("delete-event", self._on_delete_event)

        # main vbox
        vbox = gtk.VBox(False, 0)
        self._window.add(vbox)

        # description
        hbox = gtk.HBox(False, 0)
        hbox.pack_start(gtk.image_new_from_stock(gtk.STOCK_DIALOG_INFO, gtk.ICON_SIZE_DIALOG), False)
        hbox.pack_start(gtk.Label("You can now change the common name part."), False)
        vbox.pack_start(hbox, False)

        # add file list
        vbox.pack_start(self._file_list_widget)

        # hsep
        vbox.pack_start(gtk.HSeparator(), False, False, 4)

        # create previewer, and add config
        # first, try "longest common substring"
        self._current_preview = PreviewReplaceLongestSubstring(self.refresh, self.preview_invalid, self._files_model)
        # if that doesn't work, offer some common simple modifications
        if not self._current_preview.valid:
            self._logger.debug("URIs don't have a common substring, offer simple modifications instead.")
            self._current_preview = PreviewCommonModificationsSimple(self.refresh, self.preview_invalid, self._files_model)
        self.refresh()
        
        vbox.pack_start(self._current_preview.get_config_widget(), False)
        
        # hsep
        vbox.pack_start(gtk.HSeparator(), False, False, 4)
        
        # rename, cancel, and more buttons
        buttonbox = gtk.HButtonBox()
        buttonbox.set_layout(gtk.BUTTONBOX_END)
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
        cmd.insert(0, "/home/hb/src/gnome-bulk-rename/gnome-bulk-rename/gnome-bulk-rename.py") # TODO
        try:
            subprocess.Popen(cmd)
        except OSError, ee:
            print "Error: '%s' : %s" % (" ".join(cmd), ee)
            # TODO: Error dialog
            pass
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
            <menuitem action="clear"/>
        </menu>
        <menu action="help">
            <placeholder name="HelpItems"/>
            <menuitem action="about"/>
        </menu>
    </menubar>
    <toolbar name="Toolbar">
      <placeholder name="ToolbarItems"/>
      <toolitem action="add"/>
      <toolitem action="clear"/>
      <toolitem action="quit"/>
    </toolbar>
    </ui>""" % {
        "undoaction" : undo.Undo.UNDO_ACTION_NAME,
        "redoaction" : undo.Undo.REDO_ACTION_NAME,
        }

    
    def __init__(self, uris=None):
        """constructor"""
        GnomeBulkRenameAppBase.__init__(self, uris)

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
                   ("clear", gtk.STOCK_CLEAR, "Clear", None, "Removes all files from the list", self._on_action_clear),
                   ("quit", gtk.STOCK_QUIT, "_Quit", "<Control>q", "Quit the Program", self._on_action_quit),
                   ("help", None, "_Help"),
                   ("about", gtk.STOCK_ABOUT, "About", None, "About this program", self._on_action_about)
                   ]
        self._action_group.add_actions(actions)
        self._action_group.add_action(self._undo.get_undo_action())
        self._action_group.add_action(self._undo.get_redo_action())
        self._uimanager.insert_action_group(self._action_group)
        self._uimanager.add_ui_from_string(self.__ui)

        # window
        self._window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self._window.set_size_request(500, 800)
        self._window.set_border_width(5)
        self._window.connect("destroy", gtk.main_quit)
        self._window.connect("delete-event", self._on_delete_event)
        self._window.add_accel_group(self._uimanager.get_accel_group())
        
        vbox = gtk.VBox(False, 0)
        self._window.add(vbox)

        # menu bar
        vbox.pack_start(self._uimanager.get_widget("/Menubar"), False)
        vbox.pack_start(self._uimanager.get_widget("/Toolbar"), False)        
        
        # add file list widget from base class
        vbox.pack_start(self._file_list_widget)

        # hsep
        vbox.pack_start(gtk.HSeparator(), False, False, 4)

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
        hbox.pack_start(self._rename_button, False)

        # config area
        self._config_container = gtk.VBox(False, 0)
        vbox.pack_start(self._config_container, False)
        
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


    def _on_action_clear(self, dummy=None):
        self._files_model.clear()

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
        previewclass = combobox.get_model()[combobox.get_active()][constants.PREVIEWS_SELECTION_PREVIEW]
        self._current_preview = previewclass(self.refresh, self.preview_invalid, self._files_model)

        # configuration
        gtkutils.clear_gtk_container(self._config_container)
        try:
            config_widget = self._current_preview.get_config_widget()
            self._config_container.add(config_widget)
            self._config_container.show_all()
        except AttributeError:
            pass

        # refresh
        self.refresh()


    def _collect_previews(self):
        """Fill combobox with previews"""
        previews_model = self._previews_combobox.get_model()
        
        # builtin
        previews = collect.get_previews_from_modulname("preview")

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
                    previews.extend(collect.get_previews_from_modulname(modulname))
            del sys.path[0]

        # add findings
        for preview in previews:
            try:
                priority = preview.priority
            except AttributeError:
                priority = 0.5
            inserted = False
            for ii,row in enumerate(previews_model):
                if row[constants.PREVIEWS_SELECTION_PRIORITY] > priority:
                    previews_model.insert(ii, (preview.short_description, preview, priority))
                    inserted = True
                    break
            if not inserted:  
                previews_model.append((preview.short_description, preview, priority))
