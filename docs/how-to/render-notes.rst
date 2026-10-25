#############################
 Render GitHub Release notes
#############################

``notes`` turns one reviewed changelog section into a GitHub Release body. Run it from the tagged checkout so the
description matches the source that was published. It reads the changelog and prints Markdown to standard output; it
does not edit the changelog or create the GitHub Release.

A complete Markdown example
===========================

Suppose ``docs/changelog.md`` contains these two releases:

.. code-block:: markdown

    # Changelog

    <a name="release-1-2-3"></a>

    ## 1.2.3 (2026-10-18)

    <a name="release-1-2-3-fixed"></a>

    ### Fixed

    - Avoid stale cache reads ([#42](https://github.com/owner/project/pull/42)) by [@alice](https://github.com/alice).

    <a name="release-1-2-2"></a>

    ## 1.2.2 (2026-09-20)

    ### Fixed

    - Reject invalid cache keys by [@alice](https://github.com/alice).

Render only ``1.2.3``:

.. code-block:: bash

    uvx --from release-creator release-creator notes \
      --changelog docs/changelog.md \
      --tag 1.2.3 \
      --repository owner/project \
      --previous 1.2.2 \
      --artifact-url https://pypi.org/project/project/1.2.3/ \
      > release-notes.md

``--tag`` selects one section. ``--repository`` builds GitHub links. ``--previous`` selects the start of the comparison;
the :doc:`tags command <select-release-tag>` can find it. ``--artifact-url`` adds the published package link.
``release-notes.md`` contains the complete GitHub description:

.. code-block:: markdown

    <a name="release-1-2-3-fixed"></a>

    ### Bug fixes

    - Avoid stale cache reads ([#42](https://github.com/owner/project/pull/42)) by @alice.

    [PyPI release](https://pypi.org/project/project/1.2.3/)

    [Full Changelog](https://github.com/owner/project/compare/1.2.2...1.2.3)

Review that file before passing it to ``gh release create --notes-file release-notes.md``. The ``by`` credit stays in
the changelog; the GitHub body uses an ``@alice`` mention.

Rules and failure cases
=======================

The tagged changelog decides which changes appear, their order, their categories, and their authors. ``notes`` does not
infer changes or people from commits, and it does not check credits or pull request links: the ``fragments`` linker
writes them, and ``validate-news`` rejects fragments that carry their own.

``notes`` requires exactly one section for ``--tag`` and rejects unknown categories. It renames ``Fixed`` to ``Bug
fixes`` and ``Added`` to ``Features`` while keeping each release bullet on one line. For Markdown, leave empty headings
out of the tagged changelog; the supplied Towncrier template does this. The reStructuredText reader omits empty
categories. If the source section already has a ``Full Changelog`` line, ``notes`` replaces it with one link built from
``--previous`` and ``--tag``. The source's category anchors remain stable. See :doc:`the format reference
<../reference/formats>` for every category name.

Omit ``--artifact-url`` if there is no external artifact. Use ``--artifact-label`` to name another ecosystem's package
link. If ``--previous`` is absent, the final link points to the commits at this tag instead of a comparison. Artifact
links must use HTTPS.

Shared changelog with separate packages
=======================================

When packages have separate histories in one Markdown file, name the package section explicitly. For example,
``toml-fmt`` has ``## pyproject-fmt`` above ``### 2.30.4 (date)`` and ``#### Fixed``. Its Git tag is
``pyproject-fmt/2.30.4``:

.. code-block:: bash

    uvx --from release-creator release-creator notes \
      --changelog CHANGELOG.md --package pyproject-fmt \
      --tag pyproject-fmt/2.30.4 --repository tox-dev/toml-fmt \
      --previous pyproject-fmt/2.30.3 > release-notes.md

The package selector prevents a matching version in another package's history from entering the output. It does not
change the repository used for GitHub links.

New contributors
================

During release preparation, run ``contributors`` after ``towncrier build`` and before committing the changelog:

.. code-block:: bash

    uvx --from release-creator release-creator contributors \
      --changelog docs/changelog.md --version 1.2.3 --repository owner/project

The command reads the pull requests linked in the ``1.2.3`` section and asks GitHub for each one's opener and merge
time. A pull request opener is new when no merged pull request of theirs in the repository predates this one; when the
release holds several of their pull requests, only the earliest counts. Co-authors never count, and bots and AI
assistant accounts (``claude``, ``codex``, ``CommandCodeBot``, ``Copilot``) are skipped. The command needs ``gh`` with
read access to the repository and edits only Towncrier changelogs; Knope projects do not use it.

For a shared Markdown changelog, pass the package name, as in ``--package pyproject-fmt``. The command then edits the
``### 1.2.3`` section under ``## pyproject-fmt``, found as ``notes --package`` finds it, and the subsection gets a
``#### New Contributors`` heading and a ``release-pyproject-fmt-1-2-3-new-contributors`` anchor, matching that package's
categories.

When someone is new, the command appends a subsection at the end of the version section, with the same anchor and
heading markup as the categories. In Markdown:

.. code-block:: markdown

    <a name="release-1-2-3-new-contributors"></a>

    ### New Contributors

    - [@alice](https://github.com/alice) made their first contribution in [#42](https://github.com/owner/project/pull/42)

In reStructuredText, the heading uses the categories' underline character:

.. code-block:: rst

    .. _release-1-2-3-new-contributors:

    New Contributors
    ----------------

    - :user:`alice` made their first contribution in :pr:`42`

Entries follow merge order. With no new contributor, the changelog stays unchanged. ``notes`` renders the subsection
last in the release body, before the artifact and Full Changelog links. The command fails, without editing the file,
when the section already has a New Contributors subsection, so run it once per release, or when a linked pull request is
not merged.

reStructuredText changelogs
===========================

Use a ``.rst`` changelog path to select the reStructuredText reader:

.. code-block:: bash

    uvx --from release-creator release-creator notes \
      --changelog docs/changelog.rst --tag 1.2.3 \
      --repository owner/project > release-notes.md

``:issue:`` links target issues; ``:pr:`` and ``:pull:`` target pull requests. ``:user:`` becomes an ``@handle``
mention.

Nested lists stay nested. ``.. code-block::`` directives become fenced Markdown blocks inside their release items.
Top-level ``.. warning::`` directives become separate warning blocks after the preceding item.
