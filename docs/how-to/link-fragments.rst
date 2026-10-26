############################
 Link fragments after merge
############################

``fragments`` answers one question: which merged pull request introduced each changelog entry? Contributors can write
``+cache.bugfix.md`` before a pull request number exists. Run the command on the default branch after squash merge and
before Towncrier consumes the fragments. After a merge or rebase merge, the introducing commit identifies no
squash-merged PR, so the fragment gets no PR link and credits that commit's author instead.

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
associated with each commit and credits the PR author, then every other author and co-author of its merge commit in
commit order. In GitHub Actions, grant ``pull-requests: read`` and set ``GH_TOKEN`` to the workflow token. The command
edits the fragment in place:

.. code-block:: markdown

    Avoid stale cache reads ([#42](https://github.com/owner/project/pull/42)) by [@alice](https://github.com/alice).

Towncrier copies both links into the release section. Leave the credit and the pull request link out of the fragment:
``validate-news`` rejects a fragment that carries either, so only the linker writes them. The linker drops AI assistant
identities, matched on the commit email, and credits bots only when no human author remains. A co-author without a
GitHub account is credited by the trailer name as plain text. Two credits read ``X and Y``; three or more read ``X, Y
and Z``.

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

After its squash commit is associated with PR #42, the command adds the PR link and credit to the level-one heading. It
leaves the YAML front matter and any text after that heading in place. Knope then collects that heading in its release
notes. An unchanged rerun leaves the linked heading alone.

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
It also rejects a Towncrier fragment whose visible text already credits an author (``by [@alice](...)``, ``by @alice``,
or a ``:user:`alice``` role anywhere) or references a pull request (a GitHub pull request URL, ``:pr:`42```, or a bare
``#42``). It rejects text the release would mangle: the private-use character U+E000, which release notes reserve for
escaping; an unclosed Markdown code fence, which would swallow the appended link and credit; and reStructuredText that
the release notes reader reports a problem for, such as an unknown directive or role, an empty ``code-block``, or an
``include``. When the pull request changes the ``[tool.towncrier]`` table or ``towncrier.toml``, it also rejects
Towncrier ``section`` entries and a ``package`` without an explicit ``directory``. When fragments changed, it also runs
Towncrier's check against the selected base branch to catch conflicts that individual filenames cannot reveal. Set
``orphan_prefix = "+"`` and ``issue_pattern = "\\d+"`` in the Towncrier configuration. This accepts
``+topic.feature.md`` while preventing ``topic.feature.md`` from becoming an issue reference. It does not change files
or decide whether a pull request needs news; the caller uses the count with the ``skip news`` label and the PR author to
make that decision.

Write one fragment per user-visible change, including multiple changes in one pull request. Maintenance work without a
user-visible change needs no fragment. A bot pull request needs a fragment only when that pull request supplies one. The
command does not decide whether a change is newsworthy; review that before merging.

Write the Towncrier fragment as prose. The supported templates add the list bullet around it. Lists, block quotes,
tables, headings, and raw RST directives in a fragment can move its link or credit outside that item, so the PR news
check rejects them. Code blocks remain supported. Use another fragment file for another change.

For Towncrier, the linker processes filenames beginning with ``+`` and numeric filenames in the fragment directory. When
GitHub associates no squash-merged PR with a fragment's introducing commit, the linker adds no PR link and credits the
commit author after Git's mailmap: the GitHub login for a GitHub noreply email, otherwise the author name. The PR credit
rules apply: AI assistant authors get no credit, and a bot's ``[bot]`` suffix is dropped. A fragment with no introducing
commit, such as an uncommitted one, or with an AI assistant as its commit author, stays unchanged. A fragment that
already links its pull request keeps that link and gains the credit. A fragment that skipped ``validate-news`` keeps any
hand-written credit as written and gains the PR link and computed credit after it. A failed GitHub lookup stops the
command before Towncrier builds the changelog.

For Knope, the linker processes Markdown files in ``.changeset`` except ``README.md``. Each file needs YAML front matter
and a level-one heading after it. The command checks the introducing commit and computes the credit in the same way. To
validate changed changesets on a pull request, run ``release-creator validate-news --format knope --base main``. It
reads ``knope.toml``, checks each changed Markdown file's front matter type and summary, rejects hand-written credits,
pull request references, U+E000, and an unclosed code fence in its body, then prints a count. Apply the repository's
news policy to that count for both human and bot pull requests.

``validate-news`` rejects a named fragment without its ``+`` prefix before merge. Otherwise Towncrier would publish the
filename stem in place of a pull request link.

For ``123.bugfix.md``, Towncrier uses ``123`` with ``issue_format``. That number may identify an issue rather than the
merged pull request. The linker asks GitHub for the PR associated with the introducing commit. If that is PR #124, it
adds a link to PR #124 and its credit; Towncrier retains the link to issue #123. When both numbers are the same, the
template shows the link once. Use a named fragment when neither number is known.

Use ``--directory`` if the fragments are outside ``changelog.d``. In a shallow checkout the linker leaves every fragment
unchanged, because Git reports the shallow boundary commit as introducing them. Fetch the full history to get PR links
and credits.
