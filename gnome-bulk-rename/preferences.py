# GNOME bulk rename utility
# Copyright (C) 2010-2012 Holger Berndt <hb@gnome.org>
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

from gi.repository import Gtk

import constants

class Window:
    
    def __init__(self, previews_model, sorting_model, markups_model, markup_changed_cb):
        self._window = None
        self._previews_model = previews_model
        self._sorting_model = sorting_model
        self._markups_model = markups_model
        self._markup_changed_cb = markup_changed_cb
    
    
    def show(self):
        if self._window is None:
            self._setup()
        self._window.show_all()
    
    
    def _setup(self):
        
        self._window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self._window.set_position(Gtk.WindowPosition.MOUSE)
        self._window.set_title(_("Bulk Rename Preferences"))
        self._window.set_border_width(4)
        self._window.set_default_size(450, 400)

        vbox = Gtk.VBox.new(False, 0)
        self._window.add(vbox)

        notebook = Gtk.Notebook()
        vbox.pack_start(notebook, True, True, 0)

        notebook.append_page(self._setup_extensible_model_tab(self._previews_model), Gtk.Label(label=_("Previewers")))
        notebook.append_page(self._setup_extensible_model_tab(self._sorting_model, frozen_entries=["0"]), Gtk.Label(label=_("Sorting")))
        notebook.append_page(self._setup_extensible_model_tab(self._markups_model, markup=True), Gtk.Label(label=_("Markup")))

        # button box
        buttonbox = Gtk.HButtonBox()
        buttonbox.set_layout(Gtk.ButtonBoxStyle.END)
        buttonbox.set_spacing(12)
        vbox.pack_start(buttonbox, False, False, 4)
        
        close_button = Gtk.Button(stock=Gtk.STOCK_CLOSE)
        close_button.connect("clicked", lambda button, window : window.hide(), self._window)
        buttonbox.add(close_button)
        

    def _setup_extensible_model_tab(self, model, frozen_entries=None, markup=False):
        """If given, frozen_entries is a list of non-modifyable entry paths.""" 

        def toggled_callback(cell, path, model=None, frozen_entries=None):
            # ignore if entry is frozen
            if frozen_entries and path in frozen_entries:
                return
            iter = model.get_iter(path)
            is_active = not cell.get_active()
            if markup:
                if not is_active:
                    return
                for row in model:
                    row[constants.EXTENSIBLE_MODEL_COLUMN_VISIBLE] = False
            else:
                short_desc = model.get_value(iter, constants.EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION)
                if is_active:
                    model.set_value(iter, constants.EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION_MARKUP, short_desc)
                else:
                    model.set_value(iter, constants.EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION_MARKUP, "".join(['<span color="gray">', short_desc, '</span>']))
            model.set_value(iter, constants.EXTENSIBLE_MODEL_COLUMN_VISIBLE, is_active)
            if markup:
                self._markup_changed_cb(model.get_path(iter))

        def on_selection_changed(selection, infobutton):
            (model, iter) = selection.get_selected()
            if iter:
                previewclass = model.get_value(iter, constants.EXTENSIBLE_MODEL_COLUMN_OBJECT)
                infobutton.set_sensitive(hasattr(previewclass, "description"))
            else:
                infobutton.set_sensitive(False)


        def on_info_button_clicked(button, treeview):
            (model, iter) = treeview.get_selection().get_selected()
            previewclass = model.get_value(iter, constants.EXTENSIBLE_MODEL_COLUMN_OBJECT)
            dlg = Gtk.MessageDialog(parent=self._window, flags=Gtk.DialogFlags.DESTROY_WITH_PARENT, message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.CLOSE, message_format=model.get_value(iter, constants.EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION))
            dlg.format_secondary_markup(previewclass.description)
            dlg.connect("response", lambda dlg, response_id : dlg.destroy())
            dlg.show_all()

        tab_vbox = Gtk.VBox.new(False, 0)
        tab_vbox.set_border_width(12)
        scrolledwin = Gtk.ScrolledWindow()
        scrolledwin.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolledwin.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        tab_vbox.pack_start(scrolledwin, True, True, 0)
        treeview = Gtk.TreeView(model=model)
        treeview.set_headers_visible(False)
        scrolledwin.add(treeview)
        
        textrenderer = Gtk.CellRendererText()
        togglerenderer = Gtk.CellRendererToggle()
        togglerenderer.set_radio(markup)
        togglerenderer.set_property("activatable", True)
        togglerenderer.connect('toggled', toggled_callback, model, frozen_entries)
        # column "active"
        column = Gtk.TreeViewColumn(None, togglerenderer, active=constants.EXTENSIBLE_MODEL_COLUMN_VISIBLE)
        treeview.append_column(column)
        # column "original"
        column = Gtk.TreeViewColumn(None, textrenderer, markup=constants.EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION_MARKUP)
        column.set_expand(True)
        treeview.append_column(column)
        
        # information button
        buttonbox = Gtk.HButtonBox()
        buttonbox.set_layout(Gtk.ButtonBoxStyle.END)
        buttonbox.set_spacing(12)
        tab_vbox.pack_start(buttonbox, False, False, 8)
        button = Gtk.Button(stock=Gtk.STOCK_INFO)
        button.set_sensitive(False)
        button.connect("clicked", on_info_button_clicked, treeview)
        buttonbox.add(button)

        selection = treeview.get_selection()
        selection.connect("changed", on_selection_changed, button)
                
        return tab_vbox
