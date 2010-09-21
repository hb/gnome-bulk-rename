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

def get_previews_from_modulname(modulname):
    """Look for previewable objects in the module named modulname"""
    logger = logging.getLogger("gnome.bulk-rename.collect") 
    try:
        module = __import__(modulname)
    except ImportError:
        logger.error("Could not import module file: '%s'" % modulname)
        return []

    logger.debug("Inspecting module '%s'" % modulname)
    previews = []
    for entry in dir(module):
        if entry.startswith("_"):
            continue
        classobj = getattr(module, entry)
        if hasattr(classobj, "preview") and hasattr(classobj, "short_description"):
            try:
                if classobj.skip:
                    continue
            except AttributeError:
                pass
            previews.append(classobj)

    logger.debug(("`Found %d preview objects: " % len(previews))+ ", ".join([repr(previewtype) for previewtype in previews]))
    return previews
