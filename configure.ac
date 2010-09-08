AC_PREREQ(2.63)

m4_define([gbr_major_version], [0])
m4_define([gbr_minor_version], [0])
m4_define([gbr_micro_version], [1])
m4_define([gbr_version],
          [gbr_major_version.gbr_minor_version.gbr_micro_version])

AC_INIT([gnome-color-manager],[gbr_version])
AC_CONFIG_SRCDIR([gnome-bulk-rename/gnome-bulk-rename.py])
AM_INIT_AUTOMAKE([1.9 dist-bzip2])

# version
GBR_MAJOR_VERSION=gbr_major_version
GBR_MINOR_VERSION=gbr_minor_version
GBR_MICRO_VERSION=gbr_micro_version
GBR_VERSION=gbr_version
AC_SUBST(GBR_MAJOR_VERSION)
AC_SUBST(GBR_MINOR_VERSION)
AC_SUBST(GBR_MICRO_VERSION)
AC_SUBST(GBR_VERSION)

# python
AM_PATH_PYTHON(2.6)

# gettext
GETTEXT_PACKAGE=AC_PACKAGE_NAME
AC_SUBST(GETTEXT_PACKAGE)
AC_DEFINE_UNQUOTED(GETTEXT_PACKAGE, "$GETTEXT_PACKAGE", [Gettext package])
AM_GLIB_GNU_GETTEXT
IT_PROG_INTLTOOL([0.35.0])

# output
AC_CONFIG_FILES([
Makefile
po/Makefile.in
gnome-bulk-rename/Makefile
])
AC_OUTPUT
