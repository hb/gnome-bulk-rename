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

import pygtk
pygtk.require('2.0')
import gio
import gtk


import constants

def _rename(map, done_callback):
    """map is a list of (GFile, new_display_name, id)"""

    errors = []             # list of (id, error_message)
    successful_renames = [] # list of (id, gfile)
    cancellables = {}       # cancellation


    def _set_display_name_async_cb(gfile, result, user_data):
        (id, done_cb) = user_data
        try:
            new_gfile = gfile.set_display_name_finish(result)
        except gio.Error, ee:
            errors.append((id, ee.message))
        else:
            successful_renames.append((id, new_gfile))
        finally:
            # cleanup: get rid of corresponding cancellable
            del cancellables[gfile.get_uri()]
            # notify if that was the last rename (no cancellables left)
            if not cancellables:
                done_cb(successful_renames, errors)


    for (gfile, new_display_name, id) in map:

        cancellable = gio.Cancellable()
        cancellables[gfile.get_uri()] = cancellable

        gfile.set_display_name_async(new_display_name, _set_display_name_async_cb, cancellable=cancellable, user_data=(id, done_callback))

    return cancellables



class Rename(object):
    """Renames a bunch of files"""

    def __init__(self, model, two_pass=False, done_callback=None):
        """Constructor starts an async rename immediately, and returns"""
        self._model = model
        self._done_cb = done_callback
        self._num_renames = 0
        self._num_errors = 0

        self._cancellables = {}

        if not two_pass:
            self._single_pass_rename()
        else:
            self._two_pass_rename()


    def cancel(self):
        """Cancels all outstanding operations."""
        for key,cancellable in self._cancellables.iteritems():
            cancellable.cancel()


    def _single_pass_rename(self):

        def _rename_done_cb(successful_renames, errors):

            # update the model
            for id, new_gfile in successful_renames:
                self._model[id][constants.FILES_MODEL_COLUMN_ORIGINAL] = self._model[id][constants.FILES_MODEL_COLUMN_PREVIEW]
                self._model[id][constants.FILES_MODEL_COLUMN_GFILE] = new_gfile
            for id, error_msg in errors:
                self._model[id][constants.FILES_MODEL_COLUMN_ICON_STOCK] = gtk.STOCK_DIALOG_ERROR
                self._model[id][constants.FILES_MODEL_COLUMN_TOOLTIP] = "<b>ERROR:</b> " + error_msg

            # notify real caller
            self._done_cb(len(successful_renames), len(errors))


        # set up list for _rename
        rename_map = []
        for ii, row in enumerate(self._model):
            old_display_name = row[constants.FILES_MODEL_COLUMN_ORIGINAL]
            new_display_name = row[constants.FILES_MODEL_COLUMN_PREVIEW]

            # skip files that don't change name
            if old_display_name == new_display_name:
                continue

            gfile = row[constants.FILES_MODEL_COLUMN_GFILE]
            rename_map.append((gfile, new_display_name, ii))

        self._cancellables = _rename(rename_map, _rename_done_cb)




    def _two_pass_rename(self):
        raise NotImplementedError
