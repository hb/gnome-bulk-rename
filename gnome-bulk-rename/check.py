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

"""Various checks"""

import pygtk
pygtk.require('2.0')
import gtk
import gio

import constants


class Checker(object):
    """Perform various checks on a model"""

    def __init__(self, model):
        """Perform checks already in constructor"""
        # results that can be queried
        self.all_names_stay_the_same = True
        self.highest_problem_level = 0
        self.circular_uris = set()

        # common data
        self._model = model

        # run tests
        # these modify the model and/or set the results
        self._clear_all_warnings_and_errors()
        self._check_if_all_names_stay_the_same()
        # there can't be any problems in this case
        if not self.all_names_stay_the_same:

            # more common data
            self._list_of_source_uris = [(row[constants.FILES_MODEL_COLUMN_URI_DIRNAME] + row[0]) for row in model]
            self._list_of_target_uris = [(row[constants.FILES_MODEL_COLUMN_URI_DIRNAME] + row[1]) for row in model]

            self._dict_source_uri_to_index = {}
            for ii, uri in enumerate(self._list_of_source_uris):
                self._dict_source_uri_to_index[uri] = ii

            self._dict_target_uri_to_indices = {}
            for ii, uri in enumerate(self._list_of_target_uris):
                self._dict_target_uri_to_indices.setdefault(uri, []).append(ii)                    
            
            # checks
            self._check_for_double_targets()
            self._check_for_circular_renaming()
            self._check_for_already_existing_names()


    def _clear_all_warnings_and_errors(self):
        for row in self._model:
            row[constants.FILES_MODEL_COLUMN_ICON_STOCK] = None
            row[constants.FILES_MODEL_COLUMN_TOOLTIP] = None


    def _check_if_all_names_stay_the_same(self):
        for row in self._model:
            if row[0] != row[1]:
                self.all_names_stay_the_same = False
        self._all_names_stay_the_same = True


    def _check_for_double_targets(self):
        """Sets pixbuf and tooltip text. Returns True if double targets exist"""
        double_uris = []
        for key,value in self._dict_target_uri_to_indices.iteritems():
            if len(value) > 1:
                double_uris.append(key)

        msg = "<b>ERROR:</b> Double output filepath"
        registered = set()
        found_problem = False
        for uri in double_uris:
            for ii in self._dict_target_uri_to_indices[uri]:
                if ii not in registered:
                    self._model[ii][constants.FILES_MODEL_COLUMN_ICON_STOCK] = gtk.STOCK_DIALOG_ERROR
                    self.highest_problem_level = max(self.highest_problem_level, 2)
                    found_problem = True
                    if self._model[ii][constants.FILES_MODEL_COLUMN_TOOLTIP] == None:
                        self._model[ii][constants.FILES_MODEL_COLUMN_TOOLTIP] = msg
                    else:
                        self._model[ii][constants.FILES_MODEL_COLUMN_TOOLTIP] = self._model[ii][constants.FILES_MODEL_COLUMN_TOOLTIP] + "\n" + msg
                    registered.add(ii)

        return found_problem


    def _check_for_circular_renaming(self):
        self.circular_uris = set()
        # we have a circular renaming if one row's source refers to the same uri as another row's target
        set_of_source_uris = set(self._list_of_source_uris)
        set_of_target_uris = set(self._list_of_target_uris)
        possible_circular_uris = set_of_source_uris.intersection(set_of_target_uris)
        for pu in possible_circular_uris:
            if len(self._dict_target_uri_to_indices[pu]) > 1 or self._dict_source_uri_to_index[pu] != self._dict_target_uri_to_indices[pu][0]:
                self.circular_uris.add(pu)


    def _check_for_already_existing_names(self):
        """Check if a target name already exists on the file system, but is not a circular rename"""
        existing_files = set()
        for row in self._model:
            if row[0] == row[1]:
                continue
            new_name = row[constants.FILES_MODEL_COLUMN_URI_DIRNAME] + row[1]
            if new_name not in self.circular_uris:
                parent = gio.File(uri=row[constants.FILES_MODEL_COLUMN_URI_DIRNAME])
                file = parent.get_child_for_display_name(row[1])
                if file.query_exists():
                    existing_files.add(new_name)
