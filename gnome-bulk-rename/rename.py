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
            self._done_cb(results)

        # start rename
        self._cancellables = _rename(self._get_rename_info_list(files_to_rename), rename_done_cb)


    def _two_pass_rename(self, files_to_rename):
        _logger.debug("Starting two-pass rename operation")
        
        results = RenameResults(self._model, two_pass_rename=True)
        
        prefix = "gbr-%010d--" % os.getpid()

        def rename_to_final_done_cb(successful_renames, errors):
            """"Update the model and notify caller"""
            self._handle_successes(results, successful_renames)
            self._handle_errors(results, errors)
            self._done_cb(results)
        
        def rename_to_tmp_done_cb(successful_renames, errors):
            # handle errors, and queue rename operation to final name
            
            self._handle_errors(results, errors)
            
            # all successful renames to tmp names should be scheduled for renaming to the final name
            rename_to_final_info_list = []
            for success in successful_renames:
                rename_to_final_info_list.append(_RenameInfo(success.new_gfile, success.rename_info.old_display_name,
                                                             success.rename_info.new_display_name[len(prefix):],
                                                             success.rename_info.row_number))
            self._cancellables = _rename(rename_to_final_info_list, rename_to_final_done_cb)
        
        # start first rename pass
        self._cancellables = _rename(self._get_rename_info_list(files_to_rename, prefix), rename_to_tmp_done_cb)


    def _get_rename_info_list(self, files_to_rename, prefix=""):
        """Returns a list of _RenameInfo entries. New display names get an optional prefix.
        
        If files_to_rename is not None, it must be a list of GFile's. Only those files
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


    def _handle_successes(self, results, successful_renames):
        """Update model, and add to results list"""
        for el in successful_renames:
            try:
                row = self._model[el.rename_info.row_number]
            except IndexError:
                _logger.error("Model index error during rename: No row number {0}".format(el.rename_info.row_number))
                continue
            
            old_display_name = row[constants.FILES_MODEL_COLUMN_ORIGINAL]
            
            row[constants.FILES_MODEL_COLUMN_ORIGINAL] = el.rename_info.new_display_name
            row[constants.FILES_MODEL_COLUMN_GFILE] = el.new_gfile
            
            _logger.info("Renamed file from '{0}' to '{1}' (directory: {2})"
                         .format(old_display_name, el.rename_info.new_display_name,
                                 row[constants.FILES_MODEL_COLUMN_URI_DIRNAME]))
            
            results.successes.append(el)


    def _handle_errors(self, results, errors):
        """Mark errors in model, and add to results list"""
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

    def set_done_callback(self, callback):
        self._done_cb = callback
    
    def undo(self):
        _logger.debug("Starting undo")
        rename = Rename(self._rename_results.model, self._rename_results.two_pass_rename, self._rename_done_cb, self._get_reversed_rename_info_list())


    def redo(self):
        _logger.debug("Starting undo")
        rename = Rename(self._rename_results.model, self._rename_results.two_pass_rename, self._rename_done_cb, self._get_reversed_rename_info_list())


    def _rename_done_cb(self, results):
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


class _RenameError(object):
    def __init__(self, rename_info, error_msg):
        self.rename_info = rename_info
        self.error_msg = error_msg


class _RenameSuccess(object):
    def __init__(self, rename_info, new_gfile):
        self.rename_info = rename_info
        self.new_gfile = new_gfile


def _rename(rename_list, done_callback):
    """Rename files. rename_list is a list of _RenameInfo entries."""
    errors = []             # list of _RenameError entries
    successful_renames = [] # list of _RenameSuccess entries
    cancellables = {}

    def set_display_name_async_cb(gfile, result, cb_data):
        (rename_info, done_cb) = cb_data
        try:
            new_gfile = rename_info.gfile.set_display_name_finish(result)
        except RuntimeError as ee:
            errors.append(_RenameError(rename_info, ee.message))
        else:
            successful_renames.append(_RenameSuccess(rename_info, new_gfile))
        finally:
            # cleanup: get rid of corresponding cancellable
            del cancellables[rename_info.gfile.get_uri()]
            # notify if that was the last rename (no cancellables left)
            if not cancellables:
                done_cb(successful_renames, errors)
    
    for el in rename_list:
        cancellable = Gio.Cancellable()
        cancellables[el.gfile.get_uri()] = cancellable
        el.gfile.set_display_name_async(el.new_display_name, GLib.PRIORITY_DEFAULT, cancellable,
                                        set_display_name_async_cb, (el, done_callback))
    return cancellables
