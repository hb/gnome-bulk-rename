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

class Window(object):
    
    def __init__(self, previews_model):
        self._window = None
        self._previews_model = previews_model
    
    
    def show(self):
        if self._window is None:
            self._setup()
        self._window.show_all()
    
    
    def _setup(self):
        
        def toggled_callback(cell, path, model=None):
            iter = model.get_iter(path)
            is_active = not cell.get_active()
            short_desc = model.get_value(iter, constants.PREVIEWS_COLUMN_SHORT_DESCRIPTION)
            if is_active:
                model.set_value(iter, constants.PREVIEWS_COLUMN_SHORT_DESCRIPTION_MARKUP, short_desc)
            else:
                 model.set_value(iter, constants.PREVIEWS_COLUMN_SHORT_DESCRIPTION_MARKUP, "".join(['<span color="gray">', short_desc, '</span>']))
            model.set_value(iter, constants.PREVIEWS_COLUMN_VISIBLE, is_active)

        def on_selection_changed(selection, infobutton):
            (model, iter) = selection.get_selected()
            if iter:
                previewclass = model.get_value(iter, constants.PREVIEWS_COLUMN_PREVIEW)
                infobutton.set_sensitive(hasattr(previewclass, "description"))
            else:
                infobutton.set_sensitive(False)


        def on_info_button_clicked(button, treeview):
            (model, iter) = treeview.get_selection().get_selected()
            previewclass = model.get_value(iter, constants.PREVIEWS_COLUMN_PREVIEW)
            # TODO
            print previewclass.description


        self._window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self._window.set_position(gtk.WIN_POS_MOUSE)
        self._window.set_title("Bulk Rename Preferences")
        self._window.set_border_width(4)
        self._window.set_default_size(450, 400)

        vbox = gtk.VBox(False, 0)
        self._window.add(vbox)

        notebook = gtk.Notebook()
        vbox.pack_start(notebook)
        
        # Previewers
        tab_vbox = gtk.VBox(False, 0)
        notebook.append_page(tab_vbox, gtk.Label("Previewers"))
        scrolledwin = gtk.ScrolledWindow()
        scrolledwin.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        tab_vbox.pack_start(scrolledwin)
        treeview = gtk.TreeView(self._previews_model)
        treeview.set_headers_visible(False)
        scrolledwin.add(treeview)
        
        textrenderer = gtk.CellRendererText()
        togglerenderer = gtk.CellRendererToggle()
        togglerenderer.set_property("activatable", True)
        togglerenderer.connect('toggled', toggled_callback, self._previews_model)
        # column "active"
        column = gtk.TreeViewColumn(None, togglerenderer, active=constants.PREVIEWS_COLUMN_VISIBLE)
        treeview.append_column(column)
        # column "original"
        column = gtk.TreeViewColumn(None, textrenderer, markup=constants.PREVIEWS_COLUMN_SHORT_DESCRIPTION_MARKUP)
        column.set_expand(True)
        treeview.append_column(column)
        
        # information button
        buttonbox = gtk.HButtonBox()
        buttonbox.set_layout(gtk.BUTTONBOX_END)
        buttonbox.set_spacing(12)
        tab_vbox.pack_start(buttonbox, False, False, 4)
        button = gtk.Button(stock=gtk.STOCK_INFO)
        button.set_sensitive(False)
        button.connect("clicked", on_info_button_clicked, treeview)
        buttonbox.add(button)

        selection = treeview.get_selection()
        selection.connect("changed", on_selection_changed, button)
        
        # button box
        buttonbox = gtk.HButtonBox()
        buttonbox.set_layout(gtk.BUTTONBOX_END)
        buttonbox.set_spacing(12)
        vbox.pack_start(buttonbox, False, False, 4)
        
        close_button = gtk.Button(stock=gtk.STOCK_CLOSE)
        close_button.connect("clicked", lambda button, window : window.hide(), self._window)
        buttonbox.add(close_button)
