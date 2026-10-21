#################
Input formats
#################

Fragments
=========

The fragment linker accepts filenames such as ``+short-name.feature.md``. With ``--git`` it reads each fragment's
introducing squash commit. With ``--commit-map`` it reads a UTF-8 TSV with one fragment filename and one subject per
line. A subject ends with ``(#number)``. The default fragment directory is ``changelog.d``.
``--numbered-prs`` makes numeric Towncrier stems the source of PR numbers and author lookup; it leaves named
fragments tied to their introducing squash subjects.

With ``--format knope``, the default directory is ``.changeset``. A Knope fragment has a Markdown name such as
``trust-roots.md``, YAML front matter, and a level-one heading. The linker changes that heading and preserves the rest
of the file. After Knope writes ``CHANGELOG.md``, run ``release-creator anchors --changelog CHANGELOG.md`` to keep
version and category anchors attached to their headings.

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

Markdown versions use ``## 1.2.3 (date)``, ``## v1.2.3 (date)``, or ``## [1.2.3] - date`` with level-three category
headings. With ``--package``, the package heading is level two, versions are level three, and categories are level
four. Package-prefixed Git tags such as ``pyproject-fmt/2.30.4`` retain that prefix in comparison links. RST versions
use ``1.2.3 (date)`` and category headings with underlines. Historical headings may link to the Git tag with or
without a date, have two or four numeric parts (``0.2``, ``1.2.3.4``), a ``v`` prefix (``v2.0.0``), or an ``a``,
``b``, or ``rc`` suffix (``2.0.0a3``). The renderer accepts these forms when backfilling old Releases; new releases
use three-part versions. Empty categories are omitted.

Each release item belongs under a listed category. Uncategorized bullets, loose prose, and headings without entries
fail rendering, so they cannot become GitHub Release notes. A version with no entries can still render its comparison
link for historical first releases.

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
   * - Other changes
     - Other changes

Use ``Other changes`` only when converting an older uncategorized release entry whose user impact cannot be established
from its source. New fragments need a specific user-facing category or the pull request's ``skip news`` label.

GitHub output uses level-three headings and stable ``release-<version>-<category>`` anchors. Each entry may credit
one or more people with linked ``@handle`` text in the changelog; GitHub uses mentions. Bot authors are not credits.
