#################
 release-creator
#################

``release-creator`` links changelog fragments to squash pull requests, validates release tags, renders GitHub Release
notes, previews draft news in documentation, and refreshes pre-commit dependency pins.
Install a published version with ``uvx --from release-creator release-creator``.

Run each command at the stage it serves:

.. list-table:: Choose a command
    :header-rows: 1

    - - Command
      - When to run it
      - Result
    - - :doc:`fragments <how-to/link-fragments>`
      - After squash merge, before Towncrier builds the changelog
      - Adds the pull request link to each named or numbered fragment
    - - :doc:`tags <how-to/select-release-tag>`
      - Before preparing a release, then when making the comparison link
      - Checks the version or prints its predecessor
    - - :doc:`notes <how-to/render-notes>`
      - After the changelog and tag exist
      - Prints the GitHub Release body from the tagged changelog
    - - :doc:`changelog <how-to/preview-changelog>`
      - Before each pull request documentation build
      - Writes Knope history with pending changesets under Draft
    - - :doc:`marketplace <how-to/check-marketplace>`
      - Before retrying a JetBrains Marketplace plugin upload
      - Compares signed ZIP members with the published version
    - - :doc:`hooks <how-to/update-hooks>`
      - During the weekly pre-commit update
      - Updates exact hook dependency pins without rewriting other YAML

Start with the tutorial for a complete release. Use the how-to guides for an existing project. The reference lists flags
and input formats; the explanation covers the source of each part of a GitHub Release.

The :doc:`changelog <changelog>` includes an ``Unreleased`` section in PR builds when that branch has fragments.
``docs/changelog.rst`` receives those entries when the release is prepared.

.. toctree::
    :caption: Tutorial
    :hidden:

    tutorial/first-release

.. toctree::
    :caption: How-to guides
    :hidden:

    how-to/link-fragments
    how-to/render-notes
    how-to/preview-changelog
    how-to/check-marketplace
    how-to/select-release-tag
    how-to/update-hooks

.. toctree::
    :caption: Reference
    :hidden:

    reference/cli
    reference/formats

.. toctree::
    :caption: Explanation
    :hidden:

    explanation/release-data

.. toctree::
    :caption: Project
    :hidden:

    changelog
