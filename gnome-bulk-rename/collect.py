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

"""Collect previewers by introspection"""

import logging
import os.path


from gi.repository import Gio
from gi.repository import Gtk

import constants
import config
import sys


_logger = logging.getLogger("gnome.bulk-rename.collect") 


def _get_extensible_model_from_modulname(modulname, required_attributes, model=None):
    if model is None:
        model = Gtk.ListStore(*constants.EXTENSIBLE_MODEL_COLUMNS)
    
    try:
        module = __import__(modulname)
    except ImportError:
        _logger.error("Could not import module file: '%s'" % modulname)
        return model

    _logger.debug("Inspecting module '%s'" % modulname)
    found_classes = []
    for entry in dir(module):
        if entry.startswith("_"):
            continue
        classobj = getattr(module, entry)
        if hasattr(classobj, "short_description"):
            found_all_required_attributes = True
            for required_attribute in required_attributes:
                if not hasattr(classobj, required_attribute):
                    found_all_required_attributes = False
                    break

            if found_all_required_attributes:                
                try:
                    if classobj.ignore:
                        continue
                except AttributeError:
                    pass

                found_classes.append(classobj)

    _logger.debug(("`Found %d objects: " % len(found_classes))+ ", ".join([repr(classtype) for classtype in found_classes]))
    
    # add to model
    for found_class in found_classes:
        try:
            priority = found_class.priority
        except AttributeError:
            priority = 0.5
            
        try:
            skip = found_class.skip
        except AttributeError:
            skip = False
        
        if skip:
            markup = "".join(['<span color="gray">', found_class.short_description, '</span>'])
        else:
            markup = found_class.short_description
        model.append((found_class.short_description, found_class, priority, not skip, markup))

    return model


def get_extensible_model(modulname, required_attributes):
    """Returns a Gtk.istStore of found classes that implement a specific function.
    
    These classes are searched in the builtin module 'modulname', and then
    in all .py or .pyc files in the directory config.user_data_dir/modulname.

    The attribute short_description is implicitely required.

    The sort order is set to the priority field."""
    # builtin
    model = _get_extensible_model_from_modulname(modulname, required_attributes)

    # user specific
    folder = os.path.join(config.user_data_dir, modulname)
    if not os.path.isdir(folder):
        try:
            os.makedirs(folder)
        except OSError:
            _logger.debug("Could not create '%s'" % folder)
        else:
            _logger.debug("Created '%s'" % folder)

    try:
        files = os.listdir(folder)
    except OSError:
        _logger.warning("Could not list '%s'" % folder)
    else:
        modules = set()
        for file in files:
            if file.endswith(".py"):
                modules.add(file[0:-3])
            elif file.endswith(".pyc"):
                modules.add(file[0:-4])

        sys.path.insert(0, folder)
        for found_module in modules:
            _get_extensible_model_from_modulname(found_module, required_attributes, model)
        del sys.path[0]
    
    model.set_default_sort_func(lambda model, iter1, iter2, user_data : cmp(model.get_value(iter1, constants.EXTENSIBLE_MODEL_COLUMN_PRIORITY),
                                                                 model.get_value(iter2, constants.EXTENSIBLE_MODEL_COLUMN_PRIORITY)), None)
#HHBTODO Gtk.TREE_SORTABLE_DEFAULT_SORT_COLUMN_ID auf -1 gesetzt
    model.set_sort_column_id(-1, Gtk.SortType.ASCENDING)
    return model
