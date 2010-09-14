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


def clear_warnings_errors(model):
    for row in model:
        row[5] = None
        row[6] = None

def check_for_double_targets(model):
    """Returns a list of row numbers that are doubles"""
    double_filenames = []
    dd = {}
    for ii, filename in enumerate([row[1] for row in model]):
        if filename in dd:
            dd[filename].append(ii)
            double_filenames.append(filename)
        else:
            dd[filename] = [ii]

    msg = "<b>WARNING:</b> Double output filename"
    for filename in double_filenames:
        for ii in dd[filename]:
            if not model[ii][5] == gtk.STOCK_DIALOG_ERROR:
                model[ii][5] = gtk.STOCK_DIALOG_WARNING
            if model[ii][6] == None:
                model[ii][6] = msg
            else:
                model[ii][6] = model[ii][6] + "\n" + msg
            

    

def check_for_already_existing_names(model):
    """Returns a list of row numbers whose target names already exist
    on the filesystem at the time of the check"""
    return 'TODO: check2'
