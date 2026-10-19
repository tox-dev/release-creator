#################
Input formats
#################

Fragments
=========

The fragment linker accepts filenames such as ``+short-name.feature.md``. With ``--git`` it reads each fragment's
introducing squash commit. With ``--commit-map`` it reads a UTF-8 TSV with one fragment filename and one subject per
line. A subject ends with ``(#number)``. The default fragment directory is ``changelog.d``.

The package ships Markdown and reStructuredText Towncrier templates. After installing release-creator, select the
template matching the tracked changelog in ``[tool.towncrier]``:

.. code-block:: toml

   template = "release_creator.fragments:template.jinja2"

For a ``.rst`` changelog, use ``release_creator.fragments:template.rst.jinja2`` instead. Both templates omit empty
categories and add stable version and category anchors.

For RST, set Towncrier's ``underlines`` to match the headings already in the changelog. Use ``["*", "=", "-"]``
when versions have star overlines, ``["-", "~"]`` when versions have dash underlines, or ``["=", "-", "~"]``
when versions have equals underlines. The first character marks the version and the second marks categories.

Towncrier still requires category definitions in the project's ``pyproject.toml``.

Changelog sections
==================

Markdown versions use ``## 1.2.3 (date)`` with level-three category headings. RST versions use ``1.2.3 (date)`` and
category headings with underlines. Empty categories are omitted.

.. list-table:: Category names
   :header-rows: 1

   * - Changelog
     - GitHub Release
   * - Added
     - Features
   * - Changes
     - Changes
   * - Fixed
     - Bug fixes
   * - Documentation
     - Documentation
   * - Breaking changes
     - Breaking changes
   * - Security
     - Security
   * - Performance
     - Performance
   * - Deprecated
     - Deprecations
   * - Removed
     - Removals
   * - Packaging
     - Packaging

GitHub output uses level-three headings and stable ``release-<version>-<category>`` anchors. Each entry may credit
one or more people with linked ``@handle`` text in the changelog; GitHub uses mentions. Bot authors are not credits.
