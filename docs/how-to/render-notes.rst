#############################
 Extract a changelog section
#############################

``notes`` prints the body of one release's section from a Markdown or reStructuredText changelog. Run it from the tagged
checkout so the GitHub Release describes the source that was published. It drops the version heading, keeps the text in
the changelog's own format, and changes nothing else: no link rewriting, credits, or category renames.

A Markdown example
==================

Suppose ``CHANGELOG.md`` contains these two releases:

.. code-block:: markdown

    # Changelog

    <a name="release-1-2-3"></a>

    ## 1.2.3 (2026-10-18)

    <a name="release-1-2-3-fixed"></a>

    ### Fixed

    - Avoid stale cache reads (#42)

    <a name="release-1-2-2"></a>

    ## 1.2.2 (2026-09-20)

Print only ``1.2.3``:

.. code-block:: bash

    uvx --from release-creator release-creator notes --changelog CHANGELOG.md --tag 1.2.3 > section.md

``section.md`` holds the lines between the two headings. The ``release-1-2-2`` anchor above the next heading belongs to
that release, so it is left out:

.. code-block:: markdown

    <a name="release-1-2-3-fixed"></a>

    ### Fixed

    - Avoid stale cache reads (#42)

Let GitHub add the pull request list, the credits, the new contributors, and the comparison link:

.. code-block:: bash

    gh release create 1.2.3 --verify-tag --title v1.2.3 --notes-file section.md \
      --generate-notes --notes-start-tag 1.2.2

How the section is found
========================

The version comes from ``--tag`` without a ``package/`` or ``v`` prefix. A heading matches when its title starts with
that version, optionally behind a ``v``, a ``[`` or a backtick. These all match ``1.2.3``:

- ``## 1.2.3 (2026-10-18)`` and ``## v1.2.3 (2026-10-18)``;
- Keep a Changelog's ``## [1.2.3] - 2026-10-18``, with or without a link;
- reStructuredText ``1.2.3 (2026-10-18)`` with an underline, or a title with matching over- and underlines;
- a reStructuredText title that links the version to its tag, as pipx writes them.

The section ends at the next heading of the same or a higher level. Markdown levels come from the ``#`` count, ignoring
lines inside fenced code. reStructuredText levels follow the order in which each adornment style first appears, as in
Sphinx. Trailing blank lines, ``<a name>`` anchors and ``.. _label:`` targets are dropped, since they introduce the next
release. Keep a Changelog link definitions for versions and ``Unreleased``, such as ``[1.2.3]: https://...``, are
dropped wherever they appear.

The command fails unless exactly one heading matches, so a version listed twice cannot publish the wrong text. A release
without entries prints nothing and succeeds.

Shared changelog with separate packages
=======================================

When packages have separate histories in one file, name the package heading. ``toml-fmt`` has ``## pyproject-fmt`` above
``### 2.30.4 (date)`` and tags it ``pyproject-fmt/2.30.4``:

.. code-block:: bash

    uvx --from release-creator release-creator notes \
      --changelog CHANGELOG.md --package pyproject-fmt --tag pyproject-fmt/2.30.4 > section.md

Only that package's section is searched, so the same version in another package's history cannot match. A tag with a
different package prefix fails.

reStructuredText changelogs
===========================

A ``.rst`` changelog path selects the reStructuredText reader. The output is still reStructuredText; convert it before
publishing, for example with pandoc:

.. code-block:: bash

    uvx --from release-creator release-creator notes --changelog docs/changelog.rst --tag 1.2.3 |
      pandoc --sandbox -f rst -t gfm --wrap=none > section.md

Sphinx roles such as ``:pr:`` or ``:user:`` need a pandoc Lua filter to become links.
