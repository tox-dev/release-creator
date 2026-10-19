################################
Link named fragments after merge
################################

``fragments`` answers one question: which merged pull request introduced each named changelog entry? Contributors can
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

``--git`` reads the subject of the commit that added each named fragment. ``--repository`` supplies the target for
the pull request link. ``--resolve-authors`` reads the merged PR author through ``gh api`` and adds a linked human
credit when the fragment has none. In GitHub Actions, grant ``pull-requests: read`` and set ``GH_TOKEN`` to the
workflow token. The command edits the fragment in place:

.. code-block:: markdown

   Avoid stale cache reads ([#42](https://github.com/owner/project/pull/42)) by [@alice](https://github.com/alice).

Towncrier copies both links into the release section. For shared authorship, list each verified human in the fragment;
the linker checks that the list includes the merged PR author. It does not credit bot accounts. A bot PR gets no
automatic author credit, even when that PR supplies a user-visible fragment.

Rules and failure cases
=======================

Write one fragment per user-visible change, including multiple changes in one pull request. Maintenance work without
a user-visible change needs no fragment. A bot pull request needs a fragment only when that pull request supplies one.
The command does not decide whether a change is newsworthy; review that before merging.

The linker processes filenames beginning with ``+`` in the fragment directory. It requires the introducing squash
subject to end in ``(#number)`` and rejects a fragment that already links that pull request. When author resolution
is enabled, a failed GitHub lookup or a credit that omits the PR author stops the command before Towncrier builds the
changelog. The linker validates every fragment before writing any of them.

Numbered fragments also work. Towncrier gets their issue link from ``issue_format`` in ``pyproject.toml``; set that
format to the repository's issue or pull request URL. The linker does not infer an author from a numbered filename, so
write any needed ``by`` credit in the fragment itself. Use a named fragment when the pull request number is not known.

Other input sources
===================

Use ``--directory`` if the fragments are outside ``changelog.d``. If the checkout lacks Git history, supply a UTF-8
tab-separated map of fragment names to squash subjects instead of ``--git``:

.. code-block:: bash

   printf '%s\t%s\n' '+cache.bugfix.md' 'Fix stale cache reads (#42)' > commits.tsv
   uvx --from release-creator release-creator fragments \
     --repository owner/project \
     --commit-map commits.tsv

``--git`` and ``--commit-map`` are alternatives. Use one of them; the command will not guess a pull request number
from the fragment filename or from its text.
