##################
Your first release
##################

This tutorial takes a user-visible fix from a named fragment to a GitHub Release body. The example repository is
``owner/project``. It uses squash merges and has a release App or another authorized actor that can push a tag.

.. mermaid::
   :alt: A named fragment passes through a squash merge, pull request linking, and Towncrier before becoming GitHub Release notes.
   :caption: The release path
   :align: center

   flowchart LR
      fragment["Named fragment"] --> link["Squash merge + PR link"]
      link --> changelog["Tagged changelog"]
      changelog --> notes["GitHub notes"]
      classDef source fill:#dbeafe,stroke:#2563eb,color:#0f172a;
      classDef step fill:#ede9fe,stroke:#7c3aed,color:#0f172a;
      classDef result fill:#dcfce7,stroke:#16a34a,color:#0f172a;
      class fragment source;
      class link step;
      class changelog,notes result;

1. Set up the changelog format
==============================

Towncrier collects the fragments. Release-creator supplies the template, but the project chooses which categories
exist. This minimal ``pyproject.toml`` maps ``bugfix`` fragments to the ``Fixed`` category:

.. code-block:: toml

   [tool.towncrier]
   name = "project"
   directory = "changelog.d"
   filename = "docs/changelog.md"
   template = "release_creator.fragments:template.jinja2"
   title_format = false
   type = [
     { directory = "bugfix", name = "Fixed", showcontent = true },
   ]

Create ``docs/changelog.md`` with the insertion marker:

.. code-block:: markdown

   # Changelog

   <!-- towncrier release notes start -->

The marker lets Towncrier insert future releases above older ones. See :doc:`the format reference
<../reference/formats>` for the other categories.

2. Write and merge one user-visible change
==========================================

Add ``changelog.d/+cache.bugfix.md`` to the pull request:

.. code-block:: markdown

   Avoid stale cache reads by [@alice](https://github.com/alice).

The filename needs no pull request number. The sentence describes the change for users, and the linked handle credits
its author. Write another fragment if the same pull request also changes another user-visible behavior. Routine
maintenance needs no fragment.

Squash-merge the pull request as ``Fix stale cache reads (#42)``. On the default branch, link the merged PR before
Towncrier deletes the fragment:

.. code-block:: bash

   uvx --from release-creator release-creator fragments \
     --repository owner/project --git

The command finds the squash commit that introduced the file and edits the fragment to read:

.. code-block:: markdown

   Avoid stale cache reads ([#42](https://github.com/owner/project/pull/42)) by [@alice](https://github.com/alice).

It fails if the squash subject lacks ``(#42)`` or the fragment already has a PR link. See :doc:`linking named
fragments <../how-to/link-fragments>` for a checkout without Git history.

3. Check the version and build the changelog
============================================

This example contains only a bug fix, so ``--next auto`` would choose ``0.0.1``. Choose a minor bump to start the
project at ``0.1.0``. ``tags --require-newer`` then checks that no equal or newer numeric tag exists:

.. code-block:: bash

   git tag --list | uvx --from release-creator release-creator tags \
     --next minor --directory changelog.d
   git tag --list | uvx --from release-creator release-creator tags 0.1.0 --require-newer

Now let Towncrier consume the linked fragment and assemble the reviewed changelog section. The date is fixed here so
the example output is reproducible; normal release automation can use the current date.

.. code-block:: bash

   uvx --from towncrier --with release-creator towncrier build \
     --version 0.1.0 --date 2026-10-18 --yes

``docs/changelog.md`` now contains the release section, including the PR link and linked author credit:

.. code-block:: markdown

   # Changelog

   <!-- towncrier release notes start -->

   <a name="release-0-1-0"></a>

   ## 0.1.0 (2026-10-18)

   <a name="release-0-1-0-fixed"></a>

   ### Fixed

   - Avoid stale cache reads ([#42](https://github.com/owner/project/pull/42)) by [@alice](https://github.com/alice).

Format the assembled file with the project's Markdown hook, then run the full checks before committing and tagging.
The tagged file, rather than the commit list, supplies the GitHub description.

4. Render and publish the GitHub notes
======================================

After pushing the tag and publishing the package, render the notes from that tagged checkout:

.. code-block:: bash

   uvx --from release-creator release-creator notes \
     --changelog docs/changelog.md --tag 0.1.0 \
     --repository owner/project \
     --artifact-url https://pypi.org/project/project/0.1.0/ \
     > release-notes.md

``notes`` uses the ``0.1.0`` section only. It changes ``Fixed`` to the GitHub heading ``Bug fixes`` and changes the
linked author to an ``@alice`` mention. With no previous numeric release, the final link points to this tag's commits:

.. code-block:: markdown

   <a name="release-0-1-0-fixed"></a>

   ### Bug fixes

   - Avoid stale cache reads ([#42](https://github.com/owner/project/pull/42)) by @alice.

   [PyPI release](https://pypi.org/project/project/0.1.0/)

   **Full Changelog**: https://github.com/owner/project/commits/0.1.0

Review the complete body, then create the GitHub Release if the repository does not do that in its tag workflow:

.. code-block:: bash

   gh release create 0.1.0 --verify-tag --title v0.1.0 --notes-file release-notes.md

For later releases, pass ``--previous`` to compare two tags. The :doc:`tag guide <../how-to/select-release-tag>`
shows how to select that predecessor; the :doc:`notes guide <../how-to/render-notes>` covers contributor credits and
reStructuredText changelogs.
