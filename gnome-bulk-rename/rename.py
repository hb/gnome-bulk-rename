# GNOME bulk rename utility
# Copyright (C) 2010-2012 Holger Berndt <hb@gnome.org>
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

import os
import logging

from gi.repository import Gio
from gi.repository import Gtk
from gi.repository import GLib

from gettext import gettext as _

import constants


_logger = logging.getLogger("gnome.bulk-rename.rename") 

class Rename(object):
    """Renames a bunch of files asynchronically"""
    
    def __init__(self, model, two_pass=False, done_callback=None,  files_to_rename=None):
        """Constructor starts an async rename operation, and returns immediately.
        
        If files_to_rename is given, it is a list of RenameInfo objects to be
        dealt with instead of the whole model."""
        
        # disable sorting during rename
        self._sort_column_id = model.get_sort_column_id()
        model.set_sort_column_id(constants.GBR_GTK_TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID, Gtk.SortType.DESCENDING)
        
        
        self._model = model
        self._done_cb = done_callback
        self._num_renames = 0
        self._num_errors = 0
        
        self._cancellables = {}
        
        if two_pass:
            self._two_pass_rename(files_to_rename)
        else:
            self._single_pass_rename(files_to_rename)
    
    
    def cancel(self):
        """Cancels all outstanding operations."""
        for cancellable in self._cancellables.values():
            cancellable.cancel()
    
    
    def _single_pass_rename(self, files_to_rename):
        _logger.debug("Starting rename operation")
        
        results = RenameResults(self._model, two_pass_rename=False)
        
        def rename_done_cb(successful_renames, errors):
            """"Update the model and notify caller"""
            self._handle_successes(results, successful_renames)
            self._handle_errors(results, errors)
            self._restore_original_sorting()
            self._done_cb(results)

        # start rename
        manager = _RenameTaskManager(self._get_rename_info_list(files_to_rename))
        manager.start(rename_done_cb)


    def _two_pass_rename(self, files_to_rename):
        _logger.debug("Starting two-pass rename operation")
        
        results = RenameResults(self._model, two_pass_rename=True)
        
        prefix = "gbr-%010d--" % os.getpid()

        def rename_to_final_done_cb(successful_renames, errors):
            """"Update the model and notify caller"""
            self._handle_successes(results, successful_renames)
            self._handle_errors(results, errors)
            self._restore_original_sorting()
            self._done_cb(results)
        
        
        def rename_to_tmp_done_cb(successful_renames_list, errors_list):
            self._handle_errors(results, errors_list)
            
            # all successful renames to tmp names should be scheduled for renaming to the final name
            rename_to_final_info_list = []
            for successful_renames in successful_renames_list:
                for success in successful_renames:
                    rename_to_final_info_list.append(_RenameInfo(success.new_gfile, success.rename_info.old_display_name,
                                                                 success.rename_info.new_display_name[len(prefix):],
                                                                 success.rename_info.row_number))
            manager = _RenameTaskManager(rename_to_final_info_list)
            manager.start(rename_to_final_done_cb)
        
        # start first rename pass
        manager = _RenameTaskManager(self._get_rename_info_list(files_to_rename, prefix))
        manager.start(rename_to_tmp_done_cb)


    def _restore_original_sorting(self):
        if all([el is not None for el in self._sort_column_id]):
            self._model.set_sort_column_id(*self._sort_column_id)


    def _get_rename_info_list(self, files_to_rename, prefix=""):
        """Returns a list of _RenameInfo entries. New display names get an optional prefix.
        
        If files_to_rename is not None, it must be a list of _RenameInfo objects. Only those files
        will be considered instead of the complete model."""
        ll = []
        for ii, row in enumerate(self._model):
            
            if files_to_rename:
                # check if that file is also in files_to_rename list
                try:
                    rename_info = next(filter(lambda el : row[constants.FILES_MODEL_COLUMN_GFILE].equal(el.gfile), files_to_rename))
                except StopIteration:
                    continue
                if rename_info.old_display_name == rename_info.new_display_name:
                    continue
                rename_info.row_number = ii
                ll.append(rename_info)
                
            else:
                old_display_name = row[constants.FILES_MODEL_COLUMN_ORIGINAL]
                new_display_name = row[constants.FILES_MODEL_COLUMN_PREVIEW]

                # skip files that don't change name
                if old_display_name == new_display_name:
                    continue

                ll.append(_RenameInfo(row[constants.FILES_MODEL_COLUMN_GFILE], old_display_name, new_display_name, ii))
        
        if prefix:
            for el in ll:
                el.new_display_name = prefix+el.new_display_name
        
        return ll


    def _handle_successes(self, results, successful_renames_list):
        """Update model, and add to results list"""
        for successful_renames in successful_renames_list:
            for el in successful_renames:
                try:
                    row = self._model[el.rename_info.row_number]
                except IndexError:
                    _logger.error("Model index error during rename: No row number {0}".format(el.rename_info.row_number))
                    continue
                
                old_display_name = row[constants.FILES_MODEL_COLUMN_ORIGINAL]
    
                row[constants.FILES_MODEL_COLUMN_ORIGINAL] = el.rename_info.new_display_name
                row[constants.FILES_MODEL_COLUMN_GFILE] = el.new_gfile
                
                _logger.info("Renamed file from '{0}' to '{1}' (directory uri: {2})"
                             .format(old_display_name, el.rename_info.new_display_name,
                                     row[constants.FILES_MODEL_COLUMN_URI_DIRNAME]))
                
                results.successes.append(el)


    def _handle_errors(self, results, errors_list):
        """Mark errors in model, and add to results list"""
        for errors in errors_list:
            for el in errors:
                try:
                    row = self._model[el.rename_info.row_number]
                except IndexError:
                    _logger.error("Model index error during rename: No row number {0}".format(el.rename_info.row_number))
                    continue
                
                old_display_name = row[constants.FILES_MODEL_COLUMN_ORIGINAL]
                
                row[constants.FILES_MODEL_COLUMN_ICON_STOCK] = Gtk.STOCK_DIALOG_ERROR
                row[constants.FILES_MODEL_COLUMN_TOOLTIP] = "<b>{0}: {1}</b> ".format(_("ERROR"), GLib.markup_escape_text(el.error_msg))
                
                _logger.warning("Could not rename file from '{0}' to '{1}': '{2}' (directory: {3})"
                                .format(old_display_name, el.rename_info.new_display_name,
                                        el.error_msg, row[constants.FILES_MODEL_COLUMN_URI_DIRNAME]))
            results.errors.extend(errors)


class RenameUndoAction(object):
    def __init__(self, rename_results):
        self._rename_results = rename_results
        self._done_cb = None

        self._current_renamer = None
        
    def set_done_callback(self, callback):
        self._done_cb = callback
    
    def undo(self):
        _logger.debug("Starting undo")
        self._current_renamer = Rename(self._rename_results.model, self._rename_results.two_pass_rename, self._rename_done_cb, self._get_reversed_rename_info_list())


    def redo(self):
        _logger.debug("Starting redo")
        self._current_renamer = Rename(self._rename_results.model, self._rename_results.two_pass_rename, self._rename_done_cb, self._get_reversed_rename_info_list())


    def _rename_done_cb(self, results):
        self._current_renamer = None
        
        self._rename_results = results
        self._done_cb(results, self)


    def _get_reversed_rename_info_list(self):
        return [_RenameInfo(el.new_gfile, el.rename_info.new_display_name, el.rename_info.old_display_name, None) for el in self._rename_results.successes]


class RenameResults(object):
    """An object representing the results of a rename operation."""
    def __init__(self, model, two_pass_rename):
        self.model = model
        self.two_pass_rename = two_pass_rename
        
        self.successes = [] # list of _RenameSuccess
        self.errors = []    # list of _RenameError


class _RenameInfo(object):
    """An object representing information about a rename operation."""
    
    def __init__(self, gfile, old_display_name, new_display_name, row_number):
        self.gfile = gfile
        self.old_display_name = old_display_name
        self.new_display_name = new_display_name
        self.row_number = row_number
    
    def __str__(self):
        return "old/new: {0} - {1}, row {2}, gfile: {3}".format(self.old_display_name, self.new_display_name, self.row_number, self.gfile.get_uri())


class _RenameError(object):
    def __init__(self, rename_info, error_msg):
        self.rename_info = rename_info
        self.error_msg = error_msg


class _RenameSuccess(object):
    def __init__(self, rename_info, new_gfile):
        self.rename_info = rename_info
        self.new_gfile = new_gfile
    
    def __str__(self):
        return "new_gfile: {0}, {1}".format(self.new_gfile.get_uri(), str(self.rename_info))



class _RenameTaskManager(object):
    def __init__(self, rename_list):
        self._tasks = self._create_rename_tasks_list(rename_list)

        self._done_cb = None
        self._current_task = None
        self._successful_renames_list = []
        self._errors_list = []
    
    
    def start(self, done_callback):
        assert self._tasks

        self._done_cb = done_callback
        self._start_next_task()
    
    
    def cancel(self):
        raise NotImplementedError
    
    
    def _start_next_task(self):
        self._current_task = self._tasks.pop(0)
        self._current_task.start(self._task_done_cb)
        
    
    def _task_done_cb(self, successful_renames, errors):
        # successful renames
        # iterate over previous renames, modifying the path if a new rename is a prefix of an old rename
        for old_successful_renames in self._successful_renames_list:
            for old_success in old_successful_renames:
                for success in successful_renames:
                    if old_success.new_gfile.has_prefix(success.rename_info.gfile):
                        old_uri = old_success.new_gfile.get_uri()
                        rel_path = success.rename_info.gfile.get_relative_path(old_success.new_gfile)
                        old_success.new_gfile = success.new_gfile.resolve_relative_path(rel_path)
                        _logger.debug("Prefix {0} got renamed; switched new uri from {1} to {2}"
                                      .format(success.rename_info.gfile.get_uri(),
                                              old_uri,
                                              old_success.new_gfile.get_uri()))
        self._successful_renames_list.append(successful_renames)
        self._errors_list.append(errors)
        
        if self._tasks:
            self._start_next_task()
        else:
            if self._done_cb is not None:
                self._done_cb(self._successful_renames_list, self._errors_list)
                
    
    @staticmethod
    def _create_rename_tasks_list(rename_list):
        # Create rename tasks which, when executed in order, don't pose
        # problems to the rename process (for example, don't rename a folder
        # and then a file in that folder, because the path of that file wouldn't
        # exist anymore by then.

        rename_list = list(rename_list)

        tasks_list = []
        
        # first: grab all files, they can't cause any harm
        entries = []
        for ii, el in enumerate(rename_list):
            if el.gfile.query_file_type(Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, None) != Gio.FileType.DIRECTORY:
                entries.append(el)
                rename_list[ii] = None
        if entries:
            tasks_list.append(entries)
        #condense list
        rename_list = [el for el in rename_list if el is not None]
        
        # next: all directories that are not prefixes of any other directory
        found_prefix = True
        while rename_list:
            entries = []
            for ii, el in enumerate(rename_list):
                found_prefix = False
                if el is None:
                    continue
                for jj, el2 in enumerate(rename_list):
                    
                    if el2 is None or ii == jj:
                        continue
                    
                    # if el is not a prefix of any other file, it's safe
                    if el2.gfile.has_prefix(el.gfile) and not el2.gfile.equal(el.gfile):
                        found_prefix = True
                        break
                
                if not found_prefix:
                    entries.append(el)
                    rename_list[ii] = None
            rename_list = [el for el in rename_list if el is not None]
            if entries:
                tasks_list.append(entries)
                
        assert len(rename_list) == 0
        return [_RenameTask(el) for el in tasks_list]


class _RenameTask(object):
    def __init__(self, task):
        """task is a list of RenameInfo objects"""
        self._task = task
        self._done_cb = None

        self._errors = []             # list of _RenameError entries
        self._successful_renames = [] # list of _RenameSuccess entries
        self._cancellables = {}
        
    
    
    def start(self, done_callback):
        """Start rename task"""
        self._done_cb = done_callback
        for el in self._task:
            cancellable = Gio.Cancellable()
            self._cancellables[el.gfile.get_uri()] = cancellable
            el.gfile.set_display_name_async(el.new_display_name, GLib.PRIORITY_DEFAULT, cancellable,
                                            self._set_display_name_async_cb, el)


    def cancel(self):
        """Cancel ongoing rename task"""
        raise NotImplementedError


    def _set_display_name_async_cb(self, gfile, result, rename_info):
        try:
            new_gfile = rename_info.gfile.set_display_name_finish(result)
        except RuntimeError as ee:
            self._errors.append(_RenameError(rename_info, ee.message))
        else:
            self._successful_renames.append(_RenameSuccess(rename_info, new_gfile))
        finally:
            # cleanup: get rid of corresponding cancellable
            del self._cancellables[rename_info.gfile.get_uri()]
            # notify if that was the last rename (no cancellables left)
            if not self._cancellables and self._done_cb is not None:
                self._done_cb(self._successful_renames, self._errors)
