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

import os
import logging

import pygtk
pygtk.require('2.0')
import gio
import gtk


import constants


_logger = logging.getLogger("gnome.bulk-rename.rename") 


def _rename(rename_map, done_callback):
    """rename_map is a list of (GFile, new_display_name, user_data)
    
    This function doesn't care for the user_data. The caller may store stuff there,
    to make it easier to recognize the results in the end."""

    errors = []             # list of (id, error_message)
    successful_renames = [] # list of (id, gfile)
    cancellables = {}       # cancellation


    def _set_display_name_async_cb(gfile, result, cb_data):
        (user_data, done_cb) = cb_data
        try:
            new_gfile = gfile.set_display_name_finish(result)
        except gio.Error, ee:
            errors.append((user_data, ee.message))
        else:
            successful_renames.append((user_data, new_gfile))
        finally:
            # cleanup: get rid of corresponding cancellable
            del cancellables[gfile.get_uri()]
            # notify if that was the last rename (no cancellables left)
            if not cancellables:
                done_cb(successful_renames, errors)


    for (gfile, new_display_name, user_data) in rename_map:

        cancellable = gio.Cancellable()
        cancellables[gfile.get_uri()] = cancellable

        gfile.set_display_name_async(new_display_name, _set_display_name_async_cb, cancellable=cancellable, user_data=(user_data, done_callback))

    return cancellables


class RenameUndoAction(object):
    def __init__(self, rename_results):
        self._rename_results = rename_results
        self._done_cb = None
        self._id_to_names = {}


    def set_done_callback(self, callback):
        self._done_cb = callback

        
    def undo(self):
        def _rename_done_cb(results):
            self._rename_results = results
            self._done_cb(results, self)

        # set up list
        _logger.debug("Starting undo")
        rename = Rename(self._rename_results.model, self._rename_results.two_pass_rename, _rename_done_cb, self._set_up_list())


    def redo(self):
        def _rename_done_cb(results):
            self._rename_results = results
            self._done_cb(results, self)

        # set up list
        _logger.debug("Starting redo")
        rename = Rename(self._rename_results.model, self._rename_results.two_pass_rename, _rename_done_cb, self._set_up_list())


    def _set_up_list(self):
        rename_map = []
        for folder_uri, old_name, new_name in self._rename_results.rename_data:
            rename_map.append((folder_uri, new_name, old_name))
        return rename_map
        
        

class RenameResults(object):
    """An object representing the results of a rename operation"""
    def __init__(self, model, two_pass_rename):
        self.model = model
        self.two_pass_rename = two_pass_rename
        self.rename_data = [] # list of (folder_uri, old_name, new_name) for successful renames
        self.errors = [] # list of ((row, folder_uri, old_name, new_name), error_msg)


class Rename(object):
    """Renames a bunch of files"""

    def __init__(self, model, two_pass=False, done_callback=None, files_to_rename=None):
        """Constructor starts an async rename immediately, and returns.
        
        If files_to_rename is given, it is a list of (folder_uri, old_name, new_name) to be
        dealt with instead of the whole model."""
        self._model = model
        self._done_cb = done_callback
        self._num_renames = 0
        self._num_errors = 0

        self._cancellables = {}

        if not two_pass:
            self._single_pass_rename(files_to_rename)
        else:
            self._two_pass_rename()


    def cancel(self):
        """Cancels all outstanding operations."""
        for key,cancellable in self._cancellables.iteritems():
            cancellable.cancel()


    def _single_pass_rename(self, files_to_rename):

        results = RenameResults(self._model, two_pass_rename=False)

        def _rename_done_cb(successful_renames, errors):

            # update the model
            for dat, new_gfile in successful_renames:
                (iRow, folder_uri, old_display_name, new_display_name) = dat
                results.rename_data.append((folder_uri, old_display_name, new_display_name))
                if iRow is not None:
                    self._model[iRow][constants.FILES_MODEL_COLUMN_ORIGINAL] = new_display_name
                    self._model[iRow][constants.FILES_MODEL_COLUMN_GFILE] = new_gfile
                _logger.debug("Renamed '%s/%s' to '%s'" % (folder_uri, old_display_name, new_display_name))
                
            self._handle_rename_errors(errors)

            results.errors.extend(errors)

            # notify real caller
            self._done_cb(results)


        # set up list for _rename
        rename_map = self._get_rename_map(files_to_rename)
        self._cancellables = _rename(rename_map, _rename_done_cb)


    def _handle_rename_errors(self, errors):
        """Mark in model, and/or log in file"""
        for dat, error_msg in errors:
            (iRow, folder_uri, old_display_name, new_display_name) = dat
            if iRow is not None:
                self._model[iRow][constants.FILES_MODEL_COLUMN_ICON_STOCK] = gtk.STOCK_DIALOG_ERROR
                self._model[iRow][constants.FILES_MODEL_COLUMN_TOOLTIP] = "<b>ERROR:</b> " + error_msg
            _logger.warning("Could not rename file '%s' to '%s': '%s'" % (old_display_name, new_display_name, error_msg))


    def _find_row_number_of_gfile(self, gfile):
        """Returns row number, or None"""
        for ii,row in enumerate(self._model):
            if row[constants.FILES_MODEL_COLUMN_GFILE].equal(gfile):
                return ii
        return None


    def _get_rename_map(self, files_to_rename):
        rename_map = []
        if files_to_rename is None:
            for ii, row in enumerate(self._model):
                folder_uri = row[constants.FILES_MODEL_COLUMN_URI_DIRNAME]
                old_display_name = row[constants.FILES_MODEL_COLUMN_ORIGINAL]
                new_display_name = row[constants.FILES_MODEL_COLUMN_PREVIEW]

                # skip files that don't change name
                if old_display_name == new_display_name:
                    continue

                gfile = row[constants.FILES_MODEL_COLUMN_GFILE]
                rename_map.append((gfile, new_display_name, (ii, folder_uri, old_display_name, new_display_name)))
                
        else:
            for folder_uri, old_display_name, new_display_name in files_to_rename:

                # skip files that don't change name
                if old_display_name == new_display_name:
                    continue
                
                old_uri = folder_uri + old_display_name
                gfile = gio.File(uri=old_uri)
                rename_map.append((gfile, new_display_name, (self._find_row_number_of_gfile(gfile), folder_uri, old_display_name, new_display_name)))

        return rename_map


    def _two_pass_rename(self):

        results = RenameResults(self._model, two_pass_rename=True)

        prefix = "gbr-%10d--" % os.getpid()


        def _rename_back_on_final_errors(successful_renames, errors):
            for id, error_msg in errors:
                self._model[id][constants.FILES_MODEL_COLUMN_ICON_STOCK] = gtk.STOCK_DIALOG_ERROR
                self._model[id][constants.FILES_MODEL_COLUMN_TOOLTIP] = "<b>ERROR:</b> " + error_msg
            
            self._done_cb(len(successful_renames), len(errors), results)

        def _rename_to_final_done_cb(successful_renames, errors):
            
            # update the model
            for id, new_gfile in successful_renames:
                folder_uri = self._model[id][constants.FILES_MODEL_COLUMN_URI_DIRNAME]
                old_name = self._model[id][constants.FILES_MODEL_COLUMN_ORIGINAL]
                new_name = self._model[id][constants.FILES_MODEL_COLUMN_PREVIEW]
                results.rename_data.append((folder_uri, old_name, new_name))
                
                self._model[id][constants.FILES_MODEL_COLUMN_ORIGINAL] = new_name
                self._model[id][constants.FILES_MODEL_COLUMN_GFILE] = new_gfile
                
            for id, error_msg in errors:
                self._model[id][constants.FILES_MODEL_COLUMN_ICON_STOCK] = gtk.STOCK_DIALOG_ERROR
                self._model[id][constants.FILES_MODEL_COLUMN_TOOLTIP] = "<b>ERROR:</b> " + error_msg
                
            if errors:
                # for all errors -> rename back
                rename_back_map = []
                for irow, error_msg in errors:
                    rename_back_map.append((self._model[irow][constants.FILES_MODEL_COLUMN_GFILE],
                                            self._model[irow][constants.FILES_MODEL_COLUMN_ORIGINAL], id))
                self._cancellables = _rename(rename_back_map, _rename_back_on_final_errors)
                
            else:
                # notify real caller
                self._done_cb(len(successful_renames), len(errors), results)


        def _rename_to_tmp_done_cb(successful_renames, errors):
            
            # mark erros
            for id, error_msg in errors:
                self._model[id][constants.FILES_MODEL_COLUMN_ICON_STOCK] = gtk.STOCK_DIALOG_ERROR
                self._model[id][constants.FILES_MODEL_COLUMN_TOOLTIP] = "<b>ERROR:</b> " + error_msg

            # all successful renames to tmp names should be scheduled for renaming to final name
            rename_to_final_map = []
            for irow, new_gfile in successful_renames:
                rename_to_final_map.append((new_gfile, self._model[irow][constants.FILES_MODEL_COLUMN_PREVIEW], irow))
            self._cancellables = _rename(rename_to_final_map, _rename_to_final_done_cb)


        # set up list for _rename to temporary file
        rename_map = []
        for ii, row in enumerate(self._model):
            old_display_name = row[constants.FILES_MODEL_COLUMN_ORIGINAL]
            new_display_name = row[constants.FILES_MODEL_COLUMN_PREVIEW]

            # skip files that don't change name
            if old_display_name == new_display_name:
                continue

            gfile = row[constants.FILES_MODEL_COLUMN_GFILE]
            rename_map.append((gfile, prefix + new_display_name, ii))

        self._cancellables = _rename(rename_map, _rename_to_tmp_done_cb)
