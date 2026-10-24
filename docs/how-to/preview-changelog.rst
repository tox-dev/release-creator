##################################
 Show draft news in documentation
##################################

``changelog`` writes a documentation copy of Knope's released history with current changesets under ``Draft``. Run it
before the documentation builder on every pull request. Readers can then review the full pending text before a release;
the tracked changelog and changeset files stay untouched. When the changeset directory is empty, the copy has no
``Draft`` section.

The output must be a different path from the tracked changelog. Point the documentation site at that output path. The
command does not link named fragments to a pull request: that link and the verified human ``by`` credits are added after
the squash merge, before release preparation.

Shared Markdown changelog from Python
=====================================

For a repository with multiple packages in one ``CHANGELOG.md``, select one ``## package`` section and its matching
fragment directory:

.. code-block:: python

    from pathlib import Path

    from release_creator.changelog.preview import render_preview

    Path("pyproject-fmt/docs/changelog.md").write_text(
        render_preview(
            Path("CHANGELOG.md"), "pyproject-fmt", Path("changelog.d/pyproject-fmt")
        ),
        encoding="utf-8",
    )

The page puts pending entries under ``### Draft`` before that package's released history. It keeps the released text and
its anchors unchanged. Draft headings receive package-specific anchors such as ``draft-pyproject-fmt`` and
``draft-pyproject-fmt-added``, so links to them remain stable as new fragments arrive. Each fragment must be one
nonempty paragraph named ``+topic.feature.md`` or ``42.bugfix.md``, using a supported release category. A documentation
task can call ``release_creator.changelog.preview.render_preview`` directly when it needs to convert the resulting
Markdown for a Sphinx page. Other fragment files fail the preview; ``.gitkeep`` is ignored. A ``##`` heading inside a
fenced code example remains in that package's history. The package preview is a Python API used by toml-fmt's
documentation task; the ``changelog`` CLI serves Knope projects.

Knope Markdown changelog
========================

For ``.changeset/*.md`` files, use the category names from ``knope.toml``:

.. code-block:: bash

    uvx --from release-creator release-creator changelog \
      --changelog CHANGELOG.md --config knope.toml \
      --fragments .changeset --output site/data/changelog.md

A changeset with ``default: security`` and ``# Remove a distrusted root`` appears under the Draft section's Security
heading. Its full text remains visible. The copy retains existing release and category anchors; the draft has ``draft``
and ``draft-security`` anchors. The command rejects missing front matter, unknown types, and empty summaries.

Towncrier reStructuredText changelogs already have an upstream draft renderer. Enable Towncrier's Sphinx extension and
put its draft directive above the release notes start marker in the tracked RST page:

.. code-block:: rst

    .. towncrier-draft-entries:: Draft

    .. towncrier release notes start

No preview copy or ``changelog`` command is needed for those sites.
