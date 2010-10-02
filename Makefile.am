AUTOMAKE_OPTIONS = dist-bzip2

SUBDIRS	= bin gnome-bulk-rename po

desktopdir = $(datadir)/applications
desktop_in_files = gnome-bulk-rename.desktop.in
desktop_DATA = $(desktop_in_files:.desktop.in=.desktop)
@INTLTOOL_DESKTOP_RULE@

EXTRA_DIST = \
	NEWS \
	AUTHORS \
	RELEASE

DISTCLEANFILES = \
	intltool-extract \
    intltool-merge \
    intltool-update

CLEANFILES = \
    $(desktop_DATA)


EXTRA_DIST += \
    intltool-extract.in \
    intltool-merge.in \
    intltool-update.in \
    $(desktop_in_files)


ChangeLog:
	@echo "Implement me!"

.PHONY: ChangeLog
