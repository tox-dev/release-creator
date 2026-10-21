##########################
Link fragments after merge
##########################

``fragments`` answers one question: which merged pull request introduced each changelog entry? Contributors can
write ``+cache.bugfix.md`` before a pull request number exists. Run the command on the default branch after squash
merge and before Towncrier consumes the fragments.

What the command changes
========================

Given this fragment:

.. code-block:: markdown

   Avoid stale cache reads.

and an introducing squash subject of ``Fix stale cache reads (#42)``, run:

.. code-block:: bash

   uvx --from release-creator release-creator fragments \
     --repository owner/project \
     --git \
     --resolve-authors

``--git`` reads the subject of the commit that added each fragment. ``--repository`` supplies the target for
the pull request link. ``--resolve-authors`` reads the merged PR author through ``gh api`` and adds a linked human
credit when the fragment has none. In GitHub Actions, grant ``pull-requests: read`` and set ``GH_TOKEN`` to the
workflow token. The command edits the fragment in place:

.. code-block:: markdown

   Avoid stale cache reads ([#42](https://github.com/owner/project/pull/42)) by [@alice](https://github.com/alice).

Towncrier copies both links into the release section. For shared authorship, list each verified human in the fragment;
the linker checks that the list includes the merged PR author. It does not credit bot accounts. A bot PR gets no
automatic author credit, even when that PR supplies a user-visible fragment.

Knope changesets
================

For a Knope project, select its changeset format. The default directory becomes ``.changeset``:

.. code-block:: bash

   uvx --from release-creator release-creator fragments \
     --format knope \
     --repository owner/project \
     --git \
     --resolve-authors

For example, a ``trust-roots.md`` changeset can contain:

.. code-block:: markdown

   ---
   default: security
   ---

   # Remove a distrusted root certificate from ACME requests

After its squash commit ``Patch trust roots (#42)``, the command adds the PR link and verified human credit to the
level-one heading. It leaves the YAML front matter and any text after that heading in place. Knope then collects that
heading in its release notes. An unchanged rerun leaves the linked heading alone.

After ``knope prepare-release`` assembles the changelog, repair its stable section anchors:

.. code-block:: bash

   release-creator anchors --changelog CHANGELOG.md

Knope can insert a new version between an existing anchor and its heading. This command places a
``release-<version>`` anchor before each version heading and a ``release-<version>-<category>`` anchor before each
category heading. It moves displaced anchors back to the heading they identify. Repeating it leaves the file unchanged.

Rules and failure cases
=======================

Before merge, check the changed fragments against the Towncrier configuration:

.. code-block:: bash

   release-creator validate-news --base main

The command prints the number of added or modified fragments. It reads ``pyproject.toml`` by default; use
``--config`` for another path. It rejects unknown categories, unsupported names, and empty fragments. It does not
change files or decide whether a pull request needs news; the caller uses the count together with the ``skip news``
label and the PR author to make that decision.

Write one fragment per user-visible change, including multiple changes in one pull request. Maintenance work without
a user-visible change needs no fragment. A bot pull request needs a fragment only when that pull request supplies one.
The command does not decide whether a change is newsworthy; review that before merging.

For Towncrier, the linker processes filenames beginning with ``+`` and numeric filenames in the fragment directory. It requires the
introducing squash subject to end in ``(#number)``. A named fragment that already links its pull request is rejected;
a numeric fragment can retain an existing link. When author resolution is enabled, a failed GitHub lookup or a credit
that omits the PR author stops the command before Towncrier builds the changelog. The linker validates every fragment
before writing any of them.

For Knope, the linker processes Markdown files in ``.changeset`` except ``README.md``. Each file needs YAML front matter
and a level-one heading after it. The command checks the introducing squash subject and verified author in the same way.
To validate changed changesets on a pull request, run ``release-creator validate-news --format knope --base main``. It
reads ``knope.toml``, checks each changed Markdown file's front matter type and summary, then prints a count. Apply the
repository's news policy to that count for both human and bot pull requests.

Both ``fragments`` and ``tags --next`` reject a named fragment without its ``+`` prefix. Otherwise Towncrier would
publish the filename stem in place of a pull request link. The pull request check applies the same rule before merge.

For ``123.bugfix.md``, Towncrier uses ``123`` with ``issue_format``. That number may identify an issue rather than the
merged pull request. The linker reads the introducing squash subject to find the PR and its author. If the subject
ends in ``(#124)``, it adds a link to PR #124 and a verified human credit; Towncrier retains the link to issue #123.
When both numbers are the same, the template shows the link once. Use a named fragment when neither number is known.

If every numeric stem in a repository names its original pull request, pass ``--numbered-prs``. For a historical
``6.feature.md`` added during a later backfill, this links PR #6 and reads PR #6's author, even if the backfill
commit ends in ``(#12)``. Named fragments still use their introducing squash commits. Leave this option off when
numeric stems can name issues; it does not apply to Knope changesets.

Other input sources
===================

Use ``--directory`` if the fragments are outside ``changelog.d``. If the checkout lacks Git history, supply a UTF-8
tab-separated map of fragment names to squash subjects instead of ``--git``:

.. code-block:: bash

   printf '%s\t%s\n' '+cache.bugfix.md' 'Fix stale cache reads (#42)' > commits.tsv
   uvx --from release-creator release-creator fragments \
     --repository owner/project \
     --commit-map commits.tsv

``--git`` and ``--commit-map`` are alternatives. Use one of them; include numeric fragments in the map. The command
does not guess a pull request number from the filename or text.
