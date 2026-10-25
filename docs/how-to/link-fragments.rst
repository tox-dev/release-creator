############################
 Link fragments after merge
############################

``fragments`` answers one question: which merged pull request introduced each changelog entry? Contributors can write
``+cache.bugfix.md`` before a pull request number exists. Run the command on the default branch after squash merge and
before Towncrier consumes the fragments. Merge and rebase merges are unsupported because their introducing commit does
not identify one squash-merged PR.

What the command changes
========================

Given this fragment:

.. code-block:: markdown

    Avoid stale cache reads.

and an introducing squash commit associated with PR #42, run:

.. code-block:: bash

    uvx --from release-creator release-creator fragments \
      --repository owner/project

The command reads the introducing commit for each pending fragment in one Git query. It asks GitHub for the merged PR
associated with each commit and adds a linked human credit when the fragment has none. In GitHub Actions, grant
``pull-requests: read`` and set ``GH_TOKEN`` to the workflow token. The command edits the fragment in place:

.. code-block:: markdown

    Avoid stale cache reads ([#42](https://github.com/owner/project/pull/42)) by [@alice](https://github.com/alice).

Towncrier copies both links into the release section. Leave the credit and the pull request link out of the fragment:
``validate-news`` rejects a fragment that carries either, so only the linker writes them. It does not credit bot
accounts. A bot PR gets no automatic author credit, even when that PR supplies a user-visible fragment.

Knope changesets
================

For a Knope project, select its changeset format. The default directory becomes ``.changeset``:

.. code-block:: bash

    uvx --from release-creator release-creator fragments \
      --format knope \
      --repository owner/project

For example, a ``trust-roots.md`` changeset can contain:

.. code-block:: markdown

    ---
    default: security
    ---

    # Remove a distrusted root certificate from ACME requests

After its squash commit is associated with PR #42, the command adds the PR link and verified human credit to the
level-one heading. It leaves the YAML front matter and any text after that heading in place. Knope then collects that
heading in its release notes. An unchanged rerun leaves the linked heading alone.

After ``knope prepare-release`` assembles the changelog, repair its stable section anchors:

.. code-block:: bash

    release-creator anchors --changelog CHANGELOG.md

Knope can insert a new version between an existing anchor and its heading. This command places a ``release-<version>``
anchor before each version heading and a ``release-<version>-<category>`` anchor before each category heading. It moves
displaced anchors back to the heading they identify. Repeating it leaves the file unchanged.

Rules and failure cases
=======================

Before merge, check the changed fragments against the Towncrier configuration:

.. code-block:: bash

    release-creator validate-news --base main

The command prints the number of added or modified fragments. For Towncrier, it reads ``towncrier.toml`` when present
and otherwise reads ``pyproject.toml``. For Knope, it reads ``knope.toml``. It accepts configured Towncrier fragment
tables and the optional ``.N`` filename counter. It rejects unknown categories, unsupported names, and empty fragments.
It also rejects a Towncrier fragment whose visible text already credits an author (``by [@alice](...)``, ``by
:user:`alice```) or links a pull request (a GitHub pull request URL, ``:pr:`42```), using the same detection as the
linker. When fragments changed, it also runs Towncrier's check against the selected base branch to catch conflicts that
individual filenames cannot reveal. Set ``orphan_prefix = "+"`` and ``issue_pattern = "\\d+"`` in the Towncrier
configuration. This accepts ``+topic.feature.md`` while preventing ``topic.feature.md`` from becoming an issue
reference. It does not change files or decide whether a pull request needs news; the caller uses the count with the
``skip news`` label and the PR author to make that decision.

Before a release writer commits Towncrier's prepared patch, validate the staged fragment deletions:

.. code-block:: bash

    release-creator validate-fragment-deletions

The command reads ``towncrier.toml`` when present, otherwise ``pyproject.toml``. It accepts numbered and ``+`` named
fragments with an optional ``.N`` counter. It rejects a deleted template, nested file, unknown category, or wrong file
extension. It reads the Git index and makes no changes.

Write one fragment per user-visible change, including multiple changes in one pull request. Maintenance work without a
user-visible change needs no fragment. A bot pull request needs a fragment only when that pull request supplies one. The
command does not decide whether a change is newsworthy; review that before merging.

Write the Towncrier fragment as prose. The supported templates add the list bullet around it. Lists, block quotes,
tables, headings, and raw RST directives in a fragment can move its link or credit outside that item, so both the PR
news check and the release linker reject them. Code blocks remain supported. Use another fragment file for another
change.

For Towncrier, the linker processes filenames beginning with ``+`` and numeric filenames in the fragment directory. It
requires GitHub to identify the merged PR for its introducing commit. A named fragment that already links its pull
request is rejected; a numeric fragment can retain an existing link. A failed GitHub lookup or a credit that omits the
PR author stops the command before Towncrier builds the changelog. The linker validates every fragment before writing
any of them.

For Knope, the linker processes Markdown files in ``.changeset`` except ``README.md``. Each file needs YAML front matter
and a level-one heading after it. The command checks the introducing commit and verified author in the same way. To
validate changed changesets on a pull request, run ``release-creator validate-news --format knope --base main``. It
reads ``knope.toml``, checks each changed Markdown file's front matter type and summary, then prints a count. Apply the
repository's news policy to that count for both human and bot pull requests.

Both ``fragments`` and ``tags --next`` reject a named fragment without its ``+`` prefix. Otherwise Towncrier would
publish the filename stem in place of a pull request link. The pull request check applies the same rule before merge.

For ``123.bugfix.md``, Towncrier uses ``123`` with ``issue_format``. That number may identify an issue rather than the
merged pull request. The linker asks GitHub for the PR associated with the introducing commit. If that is PR #124, it
adds a link to PR #124 and a verified human credit; Towncrier retains the link to issue #123. When both numbers are the
same, the template shows the link once. Use a named fragment when neither number is known.

Use ``--directory`` if the fragments are outside ``changelog.d``. Fetch Git history for every pending fragment before
running the linker. Shallow checkouts are unsupported even when they contain the introducing commit.
