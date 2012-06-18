gnome_bulk_renamedir = $(libdir)/gnome-bulk-rename/python/gnome-bulk-rename

gnome_bulk_rename_PYTHON = \
	__init__.py \
	check.py \
	collect.py \
	config.py \
	constants.py \
	EXIF.py \
	gnomebulkrenameapp.py \
	gtkutils.py \
	markup.py \
	preferences.py \
	preview.py \
	register.py \
	rename.py \
	sort.py \
	undo.py \
	utils.py

BUILT_SOURCES=config.py

clean-local:
	rm -rf *.pyc *.pyo

# Automake currently doesn't support the new cache directory structure
# of Python 3.2 and later (PEP 3147), so after install, we delete the
# now ignored byte-compiled files that Automake created, and create
# the correct ones (also with and without optimization).
install-data-hook:
	find $(gnome_bulk_renamedir) -name "*.py[co]" -print0 | xargs -0 rm
	@PYTHON@ -m compileall -f $(gnome_bulk_renamedir)
	@PYTHON@ -O -m compileall -f $(gnome_bulk_renamedir)
