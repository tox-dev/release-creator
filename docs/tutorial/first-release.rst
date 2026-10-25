####################
 Your first release
####################

This tutorial takes a user-visible fix from a named fragment to a GitHub Release body. The example repository is
``owner/project``, with a release App or another authorized actor that can push a tag.

.. mermaid::
    :alt: A named fragment becomes a tagged changelog section, which with GitHub's generated notes forms the release.
    :caption: The release path
    :align: center

    flowchart LR
       fragment["Named fragment"] --> changelog["Tagged changelog"]
       changelog --> notes["Changelog section"]
       notes --> release["GitHub Release"]
       classDef source fill:#dbeafe,stroke:#2563eb,color:#0f172a;
       classDef step fill:#ede9fe,stroke:#7c3aed,color:#0f172a;
       classDef result fill:#dcfce7,stroke:#16a34a,color:#0f172a;
       class fragment source;
       class changelog,notes step;
       class release result;

1. Set up the changelog format
==============================

Towncrier collects the fragments. Release-creator supplies the template, but the project chooses which categories exist.
This minimal ``pyproject.toml`` maps ``bugfix`` fragments to the ``Fixed`` category:

.. code-block:: toml

    [tool.towncrier]
    name = "project"
    directory = "changelog.d"
    filename = "docs/changelog.md"
    template = "release_creator.fragments:template.jinja2"
    title_format = false
    orphan_prefix = "+"
    issue_pattern = "\\d+"
    type = [
      { directory = "bugfix", name = "Fixed", showcontent = true },
    ]

The orphan prefix lets a contributor name a fragment before a pull request exists. The issue pattern reserves bare
numeric stems for issue or pull request numbers, so ``topic.bugfix.md`` cannot become a misleading issue reference.

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

    Avoid stale cache reads.

The filename needs no pull request number. Write another fragment if the same pull request also changes another
user-visible behavior. Routine maintenance needs no fragment.

3. Check the version and build the changelog
============================================

This example contains only a bug fix, so ``--next auto`` would choose ``0.0.1``. Choose a minor bump to start the
project at ``0.1.0``. ``tags --require-newer`` then checks that no equal or newer numeric tag exists:

.. code-block:: bash

    git tag --list | uvx --from release-creator release-creator tags --next minor
    git tag --list | uvx --from release-creator release-creator tags 0.1.0 --require-newer

Now let Towncrier consume the fragment and assemble the reviewed changelog section. The date is fixed here so the
example output is reproducible:

.. code-block:: bash

    uvx --from towncrier --with release-creator towncrier build --version 0.1.0 --date 2026-10-18 --yes

``docs/changelog.md`` now contains the release section:

.. code-block:: markdown

    # Changelog

    <!-- towncrier release notes start -->

    <a name="release-0-1-0"></a>

    ## 0.1.0 (2026-10-18)

    <a name="release-0-1-0-fixed"></a>

    ### Fixed

    - Avoid stale cache reads.

Format the assembled file with the project's Markdown hook, then run the full checks before committing and tagging.

4. Publish the GitHub Release
=============================

After pushing the tag and publishing the package, print the section from that tagged checkout:

.. code-block:: bash

    uvx --from release-creator release-creator notes --changelog docs/changelog.md --tag 0.1.0 > section.md

Create the release with the section on top of GitHub's generated notes, which list the merged pull requests with their
authors:

.. code-block:: bash

    gh release create 0.1.0 --verify-tag --title v0.1.0 --notes-file section.md --generate-notes

For later releases, add ``--notes-start-tag`` with the previous tag. The :doc:`tag guide <../how-to/select-release-tag>`
shows how to find it; the :doc:`notes guide <../how-to/render-notes>` covers package sections and reStructuredText.
