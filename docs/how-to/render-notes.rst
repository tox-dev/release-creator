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

    **Full Changelog**: https://github.com/owner/project/compare/1.2.2...1.2.3

Review that file before passing it to ``gh release create --notes-file release-notes.md``. The ``by`` credit stays in
the changelog; the GitHub body uses an ``@alice`` mention.

Rules and failure cases
=======================

The tagged changelog decides which changes appear, their order, their categories, and their authors. ``notes`` does not
infer changes or people from commits. Add only user-visible changes to the changelog. Credit verified human authors
there; do not credit bots or reviewers for work they did not author.

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

First-time contributors
=======================

GitHub's generated notes may identify first-time contributors. Save its body and pass it as a second input:

.. code-block:: bash

    gh api -X POST repos/owner/project/releases/generate-notes \
      -f tag_name=1.2.3 --jq .body > generated-notes.md
    uvx --from release-creator release-creator notes \
      --changelog docs/changelog.md --tag 1.2.3 --repository owner/project \
      --generated-notes generated-notes.md > release-notes.md

Human ``New Contributors`` lines remain even when their PR did not need a changelog entry. Generated change lists and
the ``<!-- Release notes generated ... -->`` banner are discarded. This input never decides which changes or changelog
authors belong in the release. If GitHub omits a referenced PR from its generated notes, the tagged changelog entry must
already credit its author.

reStructuredText changelogs
===========================

Use a ``.rst`` changelog path to select the reStructuredText reader. For example, a project whose ``:issue:`` role
points to pull requests can run:

.. code-block:: bash

    uvx --from release-creator release-creator notes \
      --changelog docs/changelog.rst --tag 1.2.3 \
      --repository owner/project --issue-role pull > release-notes.md

``--issue-role pull`` changes ``:issue:`42``` links to pull requests. Without it, they target issues. ``:pr:`` and
``:pull:`` always target pull requests; ``:user:`` becomes an ``@handle`` mention.
