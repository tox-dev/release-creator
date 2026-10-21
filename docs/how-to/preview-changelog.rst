#####################################
 Show draft news in documentation
#####################################

``changelog`` writes a documentation copy of released history with the current fragments under ``Draft``. Run it before
the documentation builder on every pull request. Readers can then review the full pending text before a release; the
tracked changelog and fragment files stay untouched. When the fragment directory is empty, the copy has no ``Draft``
section.

The output must be a different path from the tracked changelog. Point the documentation site at that output path. The
command does not link named fragments to a pull request: that link and the verified human ``by`` credits are added after
the squash merge, before release preparation.

Shared Markdown changelog
=========================

When one Markdown file holds separate package histories, select the package and its fragment directory:

.. code-block:: bash

    uvx --from release-creator release-creator changelog \
      --format package --changelog CHANGELOG.md \
      --package pyproject-fmt --fragments changelog.d/pyproject-fmt \
      --output pyproject-fmt/docs/changelog.md

Only ``## pyproject-fmt`` and its released versions enter the output. A ``+python.feature.md`` fragment containing
``Support Python 3.15.`` appears before those versions:

.. code-block:: markdown

    # Changelog

    ## pyproject-fmt

    <a name="draft-pyproject-fmt"></a>

    ### Draft

    <a name="draft-pyproject-fmt-added"></a>

    #### Added

    - Support Python 3.15.

    ### 2.30.3 (2026-10-10)

    <a name="release-pyproject-fmt-2-30-3-added"></a>

    #### Added

    - Require Python 3.11.

The preview requires the same named or numbered fragment form, category, and single paragraph that the package
assembler accepts. A malformed fragment fails the documentation build instead of disappearing from the page.

Knope Markdown changelog
========================

For ``.changeset/*.md`` files, use the category names from ``knope.toml``:

.. code-block:: bash

    uvx --from release-creator release-creator changelog \
      --format knope --changelog CHANGELOG.md --config knope.toml \
      --fragments .changeset --output site/data/changelog.md

A changeset with ``default: security`` and ``# Remove a distrusted root`` appears under ``## Draft`` and
``### Security``. Its full text remains visible. The copy retains existing release and category anchors; the draft has
``draft`` and ``draft-security`` anchors. The command rejects missing front matter, unknown types, and empty summaries.

Towncrier reStructuredText changelogs already have an upstream draft renderer. Add
``.. towncrier-draft-entries:: Draft`` above ``.. towncrier release notes start`` in the tracked RST page and enable
Towncrier's Sphinx extension. No preview copy or ``changelog`` command is needed for those sites.
