###############
 Input formats
###############

Fragments
=========

``tags --next`` and ``validate-fragment-deletions`` read Towncrier fragment names such as ``+short-name.feature.md`` or
``42.bugfix.rst``, with an optional counter before the extension. The part before the category is either a number or a
name prefixed with ``+``. The default fragment directory is ``changelog.d``.

The package ships Markdown and reStructuredText Towncrier templates. Select the template matching the tracked changelog
in ``[tool.towncrier]``:

.. code-block:: toml

    template = "release_creator.fragments:template.jinja2"

For a ``.rst`` changelog, use ``release_creator.fragments:template.rst.jinja2`` instead. Both templates omit empty
categories and add stable ``release-<version>`` and ``release-<version>-<category>`` anchors. A numbered fragment ends
with its ``issue_format`` reference; a ``+name`` fragment has none, because nothing links it to a pull request. The
GitHub Release lists pull requests and credits from GitHub's generated notes instead.

For RST, set Towncrier's ``underlines`` to match the headings already in the changelog. Use ``["*", "=", "-"]`` when
versions have star overlines, ``["-", "~"]`` when versions have dash underlines, or ``["=", "-", "~"]`` when versions
have equals underlines. The first character marks the version and the second marks categories.

Towncrier still requires category definitions in the project's ``pyproject.toml``.

Changelog sections
==================

``notes`` finds a release by its version heading:

.. list-table:: Version headings
    :header-rows: 1

    - - Format
      - Example
    - - Towncrier Markdown
      - ``## 1.2.3 (2026-10-18)`` or ``## v1.2.3 (2026-10-18)``
    - - Keep a Changelog
      - ``## [1.2.3] - 2026-10-18``
    - - Package section
      - ``## pyproject-fmt`` above ``### 2.30.4 (2026-10-18)``
    - - Towncrier reStructuredText
      - ``1.2.3 (2026-10-18)`` underlined, or with matching over- and underlines

The section runs to the next heading of the same or a higher level. See :doc:`the notes guide <../how-to/render-notes>`
for how levels and trailing anchors are handled.
