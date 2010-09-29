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

"""Collect previewers by introspection"""

import logging

import pygtk
pygtk.require('2.0')
import glib
import gio
import gtk

import constants


_logger = logging.getLogger("gnome.bulk-rename.collect") 

def get_previews_from_modulname(modulname, model=None):
    """Look for previewable objects in the module named modulname"""
    if model is None:
        model = gtk.ListStore(*constants.PREVIEWS_COLUMNS)
    
    try:
        module = __import__(modulname)
    except ImportError:
        _logger.error("Could not import module file: '%s'" % modulname)
        return model

    _logger.debug("Inspecting module '%s' for previews" % modulname)
    previews = []
    for entry in dir(module):
        if entry.startswith("_"):
            continue
        classobj = getattr(module, entry)
        if hasattr(classobj, "preview") and hasattr(classobj, "short_description"):
            try:
                if classobj.ignore:
                    continue
            except AttributeError:
                pass
            previews.append(classobj)

    _logger.debug(("`Found %d preview objects: " % len(previews))+ ", ".join([repr(previewtype) for previewtype in previews]))
    
    # add to model
    for preview in previews:
        try:
            priority = preview.priority
        except AttributeError:
            priority = 0.5
            
        try:
            skip = preview.skip
        except AttributeError:
            skip = False
        
        if skip:
            markup = "".join(['<span color="gray">', preview.short_description, '</span>'])
        else:
            markup = preview.short_description
        model.append((preview.short_description, preview, priority, not skip, markup))
        
    return model


def get_sort_from_modulename(modulename):
    """Look for sortable objects in the module named modulename"""
    try:
        module = __import__(modulename)
    except ImportError:
        _logger.error("Could not import module file: '%s'" % modulename)
        return []
    
    _logger.debug("Inspecting module '%s' for loggers" % modulename)
    sorts = []
    for entry in dir(module):
        if entry.startswith("_"):
            continue
        classobj = getattr(module, entry)
        if hasattr(classobj, "sort") and hasattr(classobj, "short_description"):
            try:
                if classobj.skip:
                    continue
            except AttributeError:
                pass
            sorts.append(classobj)
    _logger.debug(("`Found %d sort objects: " % len(sorts))+ ", ".join([repr(sorttype) for sorttype in sorts]))
    return sorts
