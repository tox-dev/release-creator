##################################
 Show draft news in documentation
##################################

``changelog`` writes a documentation copy of Knope release history with the current fragments under ``Draft``. Run it
before the documentation builder on every pull request. Readers can then review the full pending text before a release;
the tracked changelog and fragment files stay untouched. When the fragment directory is empty, the copy has no ``Draft``
section.

The output must be a different path from the tracked changelog. Point the documentation site at that output path. The
command does not link named fragments to a pull request: that link and the verified human ``by`` credits are added after
the squash merge, before release preparation.

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
