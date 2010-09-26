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
import gtk

import constants

class Window(gtk.Window):
    
    def __init__(self, previews_model):
        
        def toggled_callback(cell, path, model=None):
            iter = model.get_iter(path)
            is_active = not cell.get_active()
            short_desc = model.get_value(iter, constants.PREVIEWS_COLUMN_SHORT_DESCRIPTION)
            if is_active:
                model.set_value(iter, constants.PREVIEWS_COLUMN_SHORT_DESCRIPTION_MARKUP, short_desc)
            else:
                 model.set_value(iter, constants.PREVIEWS_COLUMN_SHORT_DESCRIPTION_MARKUP, "".join(['<span color="gray">', short_desc, '</span>']))
            model.set_value(iter, constants.PREVIEWS_COLUMN_VISIBLE, is_active)

        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_position(gtk.WIN_POS_MOUSE)
        self.set_title("Bulk Rename Preferences")
        self.set_border_width(4)
        self.set_default_size(450, 400)

        notebook = gtk.Notebook()
        self.add(notebook)
        
        # Previewers
        vbox = gtk.VBox(False, 0)
        notebook.append_page(vbox, gtk.Label("Previewers"))
        scrolledwin = gtk.ScrolledWindow()
        scrolledwin.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        vbox.pack_start(scrolledwin)
        treeview = gtk.TreeView(previews_model)
        treeview.set_headers_visible(False)
        scrolledwin.add(treeview)
        
        textrenderer = gtk.CellRendererText()
        togglerenderer = gtk.CellRendererToggle()
        togglerenderer.set_property("activatable", True)
        togglerenderer.connect('toggled', toggled_callback, previews_model)
        # column "active"
        column = gtk.TreeViewColumn(None, togglerenderer, active=constants.PREVIEWS_COLUMN_VISIBLE)
        treeview.append_column(column)
        # column "original"
        column = gtk.TreeViewColumn(None, textrenderer, markup=constants.PREVIEWS_COLUMN_SHORT_DESCRIPTION_MARKUP)
        column.set_expand(True)
        treeview.append_column(column)
