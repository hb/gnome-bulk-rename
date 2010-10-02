AC_PREREQ(2.63)

m4_define([gbr_major_version], [0])
m4_define([gbr_minor_version], [0])
m4_define([gbr_micro_version], [1])
m4_define([gbr_version],
          [gbr_major_version.gbr_minor_version.gbr_micro_version])

AC_INIT([gnome-bulk-rename],[gbr_version])
AC_CONFIG_SRCDIR([gnome-bulk-rename/gnomebulkrenameapp.py])
AC_CONFIG_MACRO_DIR([m4])
AM_INIT_AUTOMAKE([1.9 dist-bzip2])

dnl version
GBR_MAJOR_VERSION=gbr_major_version
GBR_MINOR_VERSION=gbr_minor_version
GBR_MICRO_VERSION=gbr_micro_version
GBR_VERSION=gbr_version
AC_SUBST(GBR_MAJOR_VERSION)
AC_SUBST(GBR_MINOR_VERSION)
AC_SUBST(GBR_MICRO_VERSION)
AC_SUBST(GBR_VERSION)

dnl python
AM_PATH_PYTHON(2.6)

AS_AC_EXPAND(LIBDIR, $libdir)
AC_MSG_NOTICE(Storing library files in $LIBDIR)

AS_AC_EXPAND(DATADIR, $datadir)
AC_MSG_NOTICE(Storing data files in $DATADIR)

dnl gettext
GETTEXT_PACKAGE=gnome-bulk-rename
AC_SUBST(GETTEXT_PACKAGE)
AC_DEFINE_UNQUOTED(GETTEXT_PACKAGE, "$GETTEXT_PACKAGE", [Gettext package])
AM_GLIB_GNU_GETTEXT
IT_PROG_INTLTOOL([0.35.0])

AC_CONFIG_FILES([bin/gnome-bulk-rename], [chmod +x bin/gnome-bulk-rename])

dnl output
AC_CONFIG_FILES([
Makefile
bin/Makefile
po/Makefile.in
gnome-bulk-rename/Makefile
gnome-bulk-rename/config.py
])

AC_OUTPUT

dnl ==========================================================================
echo "
$PACKAGE_NAME v$VERSION:

	prefix:                 ${prefix}
	source code location:	${srcdir}
"
