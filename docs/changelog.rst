Changelog
=========

.. towncrier release notes start

.. _release-4-3-2:

4.3.2 (2026-10-30)
------------------

.. _release-4-3-2-fixed:

Fixed
~~~~~

- The ``fragments`` command links nothing and succeeds when the fragment directory does not exist, as in a checkout with
  no pending fragments, instead of failing the release (:pr:`56`) by :user:`gaborbernat`.

.. _release-4-3-1:

4.3.1 (2026-10-30)
------------------

.. _release-4-3-1-fixed:

Fixed
~~~~~

- The ``fragments`` linker reads the ``(#N)`` that ends a squash commit's subject when GitHub associates no pull request
  with that commit, and links pull request N when it merged as that commit (:pr:`55`) by :user:`gaborbernat`.

.. _release-4-3-0:

4.3.0 (2026-10-27)
------------------

.. _release-4-3-0-added:

Added
~~~~~

- Repeat ``--artifact-url``, with a matching ``--artifact-label`` for each, to list every published package on one line.
  Each package link starts with an emoji for its ecosystem, such as 🐍 for PyPI, and the comparison link now reads ``📜
  Full Changelog`` (:pr:`51`) by :user:`gaborbernat`.

.. _release-4-2-0:

4.2.0 (2026-10-26)
------------------

.. _release-4-2-0-changes:

Changes
~~~~~~~

- Knope changeset frontmatter is now read with knope's own line rule instead of a YAML parser, and release-creator no
  longer depends on PyYAML (:pr:`43`) by :user:`gaborbernat`.

.. _release-4-1-0:

4.1.0 (2026-10-26)
------------------

.. _release-4-1-0-added:

Added
~~~~~

- Every command now explains on stderr what it decided and why (:pr:`41`) by :user:`gaborbernat`.

.. _release-4-0-0:

4.0.0 (2026-10-26)
------------------

.. _release-4-0-0-added:

Added
~~~~~

- ``validate-news`` rejects a fragment or Knope changeset that contains the private-use character U+E000 or an unclosed
  Markdown code fence, and a reStructuredText fragment with a parser warning or error, such as an unknown directive or
  role, an empty ``code-block``, or an ``include``. These were caught only when preparing or publishing the release;
  ``fragments`` and ``notes`` no longer reject them (:pr:`37`) by :user:`gaborbernat`.

.. _release-4-0-0-changes:

Changes
~~~~~~~

- ``fragments``, ``validate-news`` and ``contributors`` run ``git`` and ``gh`` without looking them up on ``PATH``
  first. A missing executable now fails with the operating system's "No such file or directory" error instead of ``git
  is required`` or ``gh is required`` (:pr:`37`) by :user:`gaborbernat`.
- ``validate-news`` rejects Towncrier ``section`` entries and a ``package`` without an explicit ``directory`` only when
  the pull request changes the ``[tool.towncrier]`` table or ``towncrier.toml`` compared with ``--base`` (:pr:`37`) by
  :user:`gaborbernat`.

.. _release-4-0-0-breaking-changes:

Breaking changes
~~~~~~~~~~~~~~~~

- Remove ``tags --require-newer`` and the ``require_newer_tag`` function. ``tags <tag>`` without ``--previous`` no
  longer only validates the tag's format; it selects the predecessor like ``--previous`` (:pr:`37`) by
  :user:`gaborbernat`.
- Remove the ``validate-fragment-deletions`` command and the ``validate_fragment_deletions`` function. It only
  re-checked the release commit that release preparation itself produced (:pr:`37`) by :user:`gaborbernat`.
- The ``fragments`` linker no longer fails for a shallow checkout, a fragment without an introducing commit, or a commit
  without exactly one squash-merged pull request. A fragment whose commit has no squash-merged pull request gets no pull
  request link and credits the commit author after Git's mailmap, as the GitHub login for a GitHub noreply email and
  otherwise as the author name, dropping AI assistants and the ``[bot]`` suffix as pull request credits do. With several
  squash-merged pull requests the first is used. In a shallow checkout, and for a fragment without a commit or with an
  AI assistant author, the fragment stays unchanged. ``add_pull_request_links`` takes a new required ``commits``
  argument, and ``fragment_commits_from_git`` returns ``FragmentCommit`` values (:pr:`37`) by :user:`gaborbernat`.
- The ``fragments`` linker no longer re-checks fragments that ``validate-news`` already checked on the pull request. It
  links a structured fragment, a named fragment that already links its pull request, a name without the ``+`` prefix,
  and a fragment with several hand-written credits instead of failing. A hand-written credit stays as written, and the
  linker appends the pull request link and computed credit after it. ``tags --next`` treats a name without the ``+``
  prefix as a patch change. ``fragment_number`` is removed (:pr:`37`) by :user:`gaborbernat`.
- ``anchors`` returns a changelog without release headings unchanged instead of failing with ``no Markdown release
  headings found`` (:pr:`37`) by :user:`gaborbernat`.
- ``changelog`` no longer rejects an ``--output`` that is the tracked changelog or a ``--fragments`` directory that does
  not exist. ``render_preview`` no longer requires exactly one ``## <package>`` section: it uses the first one, and with
  none the page has no released history (:pr:`37`) by :user:`gaborbernat`.
- ``contributors`` no longer rejects a changelog path other than ``.md`` or ``.rst``, ``--package`` with a
  reStructuredText changelog, a section that already has a New Contributors subsection, a linked pull request that is
  not merged, or a reStructuredText section without a category heading. Unmerged pull requests are skipped, and the
  subsection heading falls back to a ``-`` underline (:pr:`37`) by :user:`gaborbernat`.
- ``fragments``, ``notes``, ``contributors``, ``tags`` and the changelog preview no longer reject a malformed
  ``--repository``, ``--tag``, ``--previous`` or ``--package`` value, a ``notes --package`` that does not match the
  tag's package, or a non-HTTPS ``--artifact-url``. They use the value as given (:pr:`37`) by :user:`gaborbernat`.
- ``marketplace`` no longer rejects a local plugin ZIP that contains no files; it compares it with Marketplace like any
  other archive (:pr:`37`) by :user:`gaborbernat`.
- ``notes --package`` with a reStructuredText changelog no longer fails with ``package selection requires a Markdown
  changelog``; the package is ignored (:pr:`37`) by :user:`gaborbernat`.
- ``notes`` and ``contributors`` use the first matching version section, and the first ``## <package>`` section, instead
  of requiring exactly one; a missing section now raises ``StopIteration``. ``notes`` renders an unknown category under
  its own name, passes Markdown text outside a category or item through unchanged, keeps empty Markdown categories, and
  renders reStructuredText blocks outside a category or item, and unsupported nested blocks such as a nested ``..
  warning::``, as plain text instead of failing (:pr:`37`) by :user:`gaborbernat`.
- ``tags --previous`` prints nothing for a target tag that is not a ``major.minor.patch`` release, or that names another
  package than ``--package``, instead of failing. ``tags --next`` with no pending fragments selects a patch release
  instead of failing with ``no changelog fragments to release`` (:pr:`37`) by :user:`gaborbernat`.
- ``validate-news`` no longer rejects an empty ``--base``, a Towncrier changelog filename other than ``.md`` or
  ``.rst``, a ``pyproject.toml`` without ``[tool.towncrier]``, or a ``knope.toml`` without exactly one package.
  ``validate-news`` and ``changelog`` no longer check the shape of Knope ``extra_changelog_sections``. With several
  ``[packages.<name>]`` tables, the first one is used (:pr:`37`) by :user:`gaborbernat`.

.. _release-3-2-1:

3.2.1 (2026-10-26)
------------------

.. _release-3-2-1-fixed:

Fixed
~~~~~

- The ``fragments`` linker asks GitHub about at most 40 fragment commits per GraphQL query. A batch of 50 or more
  exceeded GitHub's node limit and failed with ``MAX_NODE_LIMIT_EXCEEDED``, so release preparation with many fragments
  aborted (:pr:`36`) by :user:`gaborbernat`.
- The ``fragments`` linker skips a merge commit author that has no linked GitHub account and no name, instead of
  aborting the run with ``unnamed merge commit author`` (:pr:`36`) by :user:`gaborbernat`.
- ``contributors`` finds the version section the same way ``notes`` does, so it also accepts a leading ``v``, a
  reStructuredText title that links the version to its tree, and a Keep a Changelog ``## [1.2.3] - 2026-10-25`` heading.
  Before, it reported ``found 0`` for these changelogs (:pr:`36`) by :user:`gaborbernat`.

.. _release-3-2-1-security:

Security
~~~~~~~~

- The ``fragments`` linker also drops merge commit authors and pull request authors whose GitHub login is a known AI
  assistant (``claude``, ``codex``, ``CommandCodeBot``, ``Copilot``, in any letter case), as ``contributors`` already
  does. Before, only AI assistant commit emails were dropped. When no author remains, the linker adds the pull request
  link without a credit (:pr:`36`) by :user:`gaborbernat`.
- ``validate-news`` and the ``fragments`` linker also detect a ``by`` credit in any letter case after any non-word
  character, such as ``(by @alice)`` or ``By @alice``; a ``:user:`` role with any content, such as a display name or a
  ``[bot]`` login; ``:user:``, ``:pr:`` and ``:pull:`` role names in any letter case; a Markdown profile link whose text
  is a code span; and an HTML anchor or HTML block that links a pull request or contains ``#123``. ``validate-news``
  rejects them as hand-written attribution, and the linker treats them as already credited or linked (:pr:`36`) by
  :user:`gaborbernat`.

.. _release-3-2-0:

3.2.0 (2026-10-25)
------------------

.. _release-3-2-0-added:

Added
~~~~~

- Add ``--package`` to ``contributors``. It finds the version section inside the ``## <package>`` section of a shared
  Markdown changelog the same way ``notes --package`` does, and gives the New Contributors subsection that package's
  ``####`` heading and anchor (:pr:`35`) by :user:`gaborbernat`.

.. _release-3-2-0-fixed:

Fixed
~~~~~

- ``notes --package`` and ``contributors --package`` keep a package version anchor that sits directly after its own
  version heading inside that version's section. Before, the anchor ended the section, so ``notes`` rendered toml-fmt
  releases with only the Full Changelog link. ``notes`` leaves the version anchor out of the release body, which starts
  at the first category anchor (:pr:`35`) by :user:`gaborbernat`.

.. _release-3-1-0:

3.1.0 (2026-10-25)
------------------

.. _release-3-1-0-added:

Added
~~~~~

- Add the ``contributors`` command. After ``towncrier build``, it appends a ``New Contributors`` subsection to the new
  version's section for each pull request author, other than bots and AI assistants, whose first merged pull request in
  the repository is in this release. ``notes`` renders that subsection last in the GitHub Release body (:pr:`34`) by
  :user:`gaborbernat`.
- Restore the 2.0.0 ``fragments``, ``validate-news``, ``changelog`` and ``anchors`` commands, Knope changeset support,
  ``tags --previous``, the Towncrier templates, and the full ``notes`` rendering: reStructuredText to GitHub Markdown,
  anchors, category headings, the New Contributors section, and the artifact and Full Changelog links (:pr:`34`) by
  :user:`gaborbernat`.
- The ``fragments`` linker credits the pull request author and every human author of its merge commit, including
  ``Co-authored-by`` trailers, in commit order. It drops AI assistant identities, credits bots only when no human
  remains, and credits an author without a GitHub account by the trailer name (:pr:`34`) by :user:`gaborbernat`.

.. _release-3-1-0-security:

Security
~~~~~~~~

- ``validate-news`` and the ``fragments`` linker also detect a bare ``by @handle`` credit, a ``:user:`` role anywhere in
  the prose, and a bare ``#123`` reference, so ``validate-news`` rejects them as hand-written attribution. The rejection
  also covers the body of each changeset checked by ``validate-news --format knope`` (:pr:`34`) by :user:`gaborbernat`.
- ``validate-news`` rejects a Towncrier fragment that already credits an author or links a pull request, so only the
  ``fragments`` linker writes them (:pr:`34`) by :user:`gaborbernat`.

.. _release-3-1-0-removed:

Removed
~~~~~~~

- Remove ``notes --generated-notes``. ``notes`` no longer reads GitHub's generated notes or renders a New Contributors
  section from them; the release body contains only the tagged changelog section (:pr:`34`) by :user:`gaborbernat`.
- Remove the ``hooks`` command. Hook updates move to Dependabot's ``pre-commit`` ecosystem, and pre-commit.ci keeps
  running the hooks (:pr:`34`) by :user:`gaborbernat`.
- ``notes`` no longer checks changelog credits against GitHub's generated notes or pull request authors, pull request
  link labels against their targets, or pull requests missing from the generated notes, and drops the raw HTML and
  GitHub link path checks that served those checks (:pr:`34`) by :user:`gaborbernat`.

.. _release-3-0-0:

3.0.0 (2026-10-25)
------------------

.. _release-3-0-0-changes:

Changes
~~~~~~~

- The Towncrier templates always append the fragment's issue references, as Towncrier's own template does, since no
  linker adds them to the text any more (:pr:`33`) by :user:`gaborbernat`.

.. _release-3-0-0-breaking-changes:

Breaking changes
~~~~~~~~~~~~~~~~

- ``hooks`` rejects environment markers on direct dependencies, YAML aliases anywhere in the configuration, and
  flow-style lists that need managed pins, instead of rewriting them (:pr:`33`) by :user:`gaborbernat`.
- ``notes`` prints the tagged section in the changelog's own format without its heading and accepts only
  ``--changelog``, ``--tag`` and ``--package``. It no longer renames categories, checks credits, adds artifact or
  comparison links, or converts reStructuredText to Markdown, and drops the ``docutils``, ``markdown-it-py``,
  ``mdformat`` and ``mdformat-gfm`` dependencies (:pr:`33`) by :user:`gaborbernat`.

.. _release-3-0-0-security:

Security
~~~~~~~~

- ``hooks`` rejects dependencies that uv would read as an option, URL or path, and ``UV_*``, ``PIP_*`` or ``PYTHON*``
  keys in ``default_env`` or a hook's ``env``, since each could install packages the cooldown never checked (:pr:`33`)
  by :user:`gaborbernat`.

.. _release-3-0-0-removed:

Removed
~~~~~~~

- Remove ``tags --previous``; find the comparison base with ``git describe --tags --abbrev=0 --first-parent`` (:pr:`33`)
  by :user:`gaborbernat`.
- Remove the ``changelog`` and ``anchors`` commands and the Knope changeset support behind them (:pr:`33`) by
  :user:`gaborbernat`.
- Remove the ``fragments`` and ``validate-news`` commands; check news with ``towncrier check --compare-with`` and let
  ``gh release create --generate-notes`` credit authors. A ``+name`` fragment no longer gains a pull request link or
  ``by`` credit in the documentation changelog, and ``towncrier`` is no longer a runtime dependency (:pr:`33`) by
  :user:`gaborbernat`.
- Remove the ``locks`` command and the ``tomli-w`` dependency; generate a selectable project lock with ``nab lock``
  (:pr:`33`) by :user:`gaborbernat`.

.. _release-2-0-0:

2.0.0 (2026-10-25)
------------------

.. _release-2-0-0-changes:

Changes
~~~~~~~

- Make ``tags --next auto`` select a major release for a ``removal`` fragment, as it does for ``breaking``, because a
  removed interface breaks its callers (:pr:`32`) by :user:`gaborbernat`.

.. _release-2-0-0-fixed:

Fixed
~~~~~

- Keep a literal ``~`` from a reStructuredText changelog escaped in GitHub release notes, so GitHub does not render
  ``~text~`` as strikethrough (:pr:`32`) by :user:`gaborbernat`.
- Lock a workspace member's dependencies, and the dependencies of the project's own extras, in place of a published copy
  from PyPI when a runtime dependency or extra names that member or the project itself (:pr:`32`) by
  :user:`gaborbernat`.
- Preserve inline code spacing and HTML entity text in GitHub release notes. Keep pull request links and verified
  credits with their change item across HTML breaks. Reject fragment structures that move attribution outside
  Towncrier's list item and malformed HTML literal elements that are self-closing, unclosed, or crossed (:pr:`32`) by
  :user:`gaborbernat`.
- Resolve each ``release-*`` group under the pins of ``project-runtime`` and of the ``release-*`` groups before it, so a
  lock whose release selections cannot be installed together fails when it is refreshed rather than in the release job
  (:pr:`32`) by :user:`gaborbernat`.
- Resolve hook dependencies for a free-threaded ``language_version`` such as ``python3.14t`` instead of failing
  (:pr:`32`) by :user:`gaborbernat`.
- Treat a reStructuredText ``X.Y.Z (date)`` line as a release heading only when an adornment underlines it, so a version
  mentioned in an entry no longer ends the section (:pr:`32`) by :user:`gaborbernat`.

.. _release-2-0-0-documentation:

Documentation
~~~~~~~~~~~~~

- Restore the verified contributor credit for pull request #4 in the 0.1.1 changelog entry (:pr:`32`) by
  :user:`gaborbernat`.

.. _release-2-0-0-breaking-changes:

Breaking changes
~~~~~~~~~~~~~~~~

- Record the resolving uv version as ``uv-version`` in ``pylock.toml`` and make ``locks --check`` report a different uv
  before comparing the lock. Stop writing the ``[tool.nab]`` creation stamp. Existing locks must be refreshed (:pr:`32`)
  by :user:`gaborbernat`.
- Remove the ``locks`` options ``--project``, ``--output``, ``--tool-python``, ``--build-requirement`` and
  ``--exclude-newer-package``, which no caller used. The command reads ``pyproject.toml`` and writes ``pylock.toml`` in
  the current directory. Declare dynamic build requirements in a ``build`` dependency group and package cutoffs in
  ``[tool.release-creator.locks.exclude-newer-package]`` (:pr:`32`) by :user:`gaborbernat`.
- Remove the ``tags --next calver`` choice, which no caller used (:pr:`32`) by :user:`gaborbernat`.

.. _release-2-0-0-security:

Security
~~~~~~~~

- Check credits and links inside inline HTML elements such as ``<code>`` in GitHub release notes, since GitHub renders
  them. Reject release entries and fragments with ``<details>``, ``<summary>``, or an HTML comment left open across
  blocks, which could hide the real author behind a false credit (:pr:`32`) by :user:`gaborbernat`.
- Check the visible text of every link in GitHub release notes. A link label that shows a pull request number, such as
  ``#5``, ``(#5)``, ``GH-5`` or a pull request URL, must point to that pull request in the release repository; credits
  inside link labels and GitHub links with ``.``, ``..`` or percent-encoded path segments are rejected (:pr:`32`) by
  :user:`gaborbernat`.
- Reject ``additional_dependencies`` on a hook whose language, set in the configuration or in the hook repository's
  manifest, is not Python, because those dependencies would install unpinned and uncooled (:pr:`32`) by
  :user:`gaborbernat`.
- Reject a YAML merge key at the root of the pre-commit configuration, which hid every remote hook from the dependency
  closure check (:pr:`32`) by :user:`gaborbernat`.
- Reject managed hook dependency pins that select extras, because uv ignores extras in constraints and the extra's
  dependencies would install unpinned (:pr:`32`) by :user:`gaborbernat`.
- Reject pre-commit configurations where two hook repositories share a hook list or hook through a YAML alias, which
  resolved only one repository's dependency closure, and dependency lists that reuse an anchored entry, which received
  managed pins at the anchor (:pr:`32`) by :user:`gaborbernat`.
- Resolve locks with ``--no-python-downloads``, so ``locks`` builds source distributions only with an installed Python
  instead of fetching a managed interpreter (:pr:`32`) by :user:`gaborbernat`.

.. _release-1-1-0:

1.1.0 (2026-10-24)
------------------

.. _release-1-1-0-added:

Added
~~~~~

- Check proposed pre-commit hook dependency pins without changing the configuration (:pr:`31`) by :user:`gaborbernat`.
- Export one selectable pylock.toml for a project's runtime dependencies, groups, extras, Python range, and platforms
  (:pr:`31`) by :user:`gaborbernat`.

.. _release-1-1-0-fixed:

Fixed
~~~~~

- Ignore contextual pull request URLs when checking a changelog entry's linked author credit (:pr:`31`) by
  :user:`gaborbernat`.

.. _release-1-1-0-removed:

Removed
~~~~~~~

- Remove the unused package changelog CLI mode while keeping ``render_preview`` for Python callers (:pr:`31`) by
  :user:`gaborbernat`.

.. _release-1-0-1:

1.0.1 (2026-10-24)
------------------

.. _release-1-0-1-security:

Security
~~~~~~~~

- Keep the required pull request check distinct from dispatch and push checks, so a skipped hook cooldown cannot satisfy
  branch protection (:pr:`30`) by :user:`gaborbernat`.

.. _release-1-0-0:

1.0.0 (2026-10-24)
------------------

.. _release-1-0-0-fixed:

Fixed
~~~~~

- Accept trailing slashes and the ``www.github.com`` host in verified release-note author links (:pr:`29`) by
  :user:`gaborbernat`.
- Accept valid YAML comments and quoting in Knope changeset front matter during news validation (:pr:`29`) by
  :user:`gaborbernat`.
- Apply one author credit to adjacent pull request references separated by whitespace or semicolons (:pr:`29`) by
  :user:`gaborbernat`.
- Do not count reviewer mentions as pull request author credits (:pr:`29`) by :user:`gaborbernat`.
- Escape URL punctuation when converting reStructuredText links to GitHub release Markdown (:pr:`29`) by
  :user:`gaborbernat`.
- Finalize a CalVer prerelease in the current month before incrementing its patch number (:pr:`29`) by
  :user:`gaborbernat`.
- Find the introducing commit for renamed fragments and fragments whose filenames contain non-ASCII characters
  (:pr:`29`) by :user:`gaborbernat`.
- Identify fragment commits by full path so nested files with the same name cannot change pull request attribution
  (:pr:`29`) by :user:`gaborbernat`.
- Ignore numeric fragments of unrelated bare URLs when checking release-note pull request credits (:pr:`29`) by
  :user:`gaborbernat`.
- Ignore pull request references inside code when linking changelog fragments (:pr:`29`) by :user:`gaborbernat`.
- Keep a numbered issue in a changelog entry when its digits only appear as the start of a longer pull request number
  (:pr:`29`) by :user:`gaborbernat`.
- Keep direct dependencies in a flow-style list when a trailing comment contains the managed-pin marker (:pr:`29`) by
  :user:`gaborbernat`.
- Keep fenced package headings inside their changelog section and reject unsupported pending fragment files in
  documentation previews (:pr:`29`) by :user:`gaborbernat`.
- Keep generated hook dependency pins with a folded or literal dependency item when another YAML key follows it
  (:pr:`29`) by :user:`gaborbernat`.
- Keep literal tildes in reStructuredText changelog entries when rendering GitHub Markdown (:pr:`29`) by
  :user:`gaborbernat`.
- Leave fenced code examples unchanged when repairing Markdown release anchors (:pr:`29`) by :user:`gaborbernat`.
- Match explicit GitHub author credits without case sensitivity and treat GitHub mannequin authors as unavailable
  accounts (:pr:`29`) by :user:`gaborbernat`.
- Pin ranged and unpinned Python hook dependencies before they run in release preparation. Preserve the caller's version
  range across updates and reject YAML aliases that share an edited dependency list (:pr:`29`) by :user:`gaborbernat`.
- Preserve comments on direct dependencies when updating a flow-style hook mapping (:pr:`29`) by :user:`gaborbernat`.
- Preserve wrapped reStructuredText release notes and verify credits on short, repository-prefixed, and issue-form pull
  request links. Ignore pull request syntax inside code spans and blocks when checking credits (:pr:`29`) by
  :user:`gaborbernat`.
- Reject misleading pull request labels and GitHub author links after resolving Markdown references and nested markup
  (:pr:`29`) by :user:`gaborbernat`.
- Reject raw HTML hyperlinks in release entries so an ``@handle`` credit cannot point to another person (:pr:`29`) by
  :user:`gaborbernat`.
- Reject release-note lines that embed markup inside a category anchor (:pr:`29`) by :user:`gaborbernat`.
- Reject unsupported or empty changelog fragments in the pull request news check (:pr:`29`) by :user:`gaborbernat`.
- Render package release anchors when the package name contains underscores (:pr:`29`) by :user:`gaborbernat`.
- Require the merged pull request author in the fragment's author list; a later reviewer mention does not count as a
  credit (:pr:`29`) by :user:`gaborbernat`.
- Rerun eligible hook cooldown checks daily so an unchanged bot update can become mergeable after seven days (:pr:`29`)
  by :user:`gaborbernat`.
- Resolve Python hook dependencies for the manifest's ``language_version`` when the caller does not override it
  (:pr:`29`) by :user:`gaborbernat`.
- Resolve hook dependencies from PyPI even when the caller sets uv or pip index and resolver environment variables
  (:pr:`29`) by :user:`gaborbernat`.
- Stop package release notes at the next version anchor, even when the following heading is missing (:pr:`29`) by
  :user:`gaborbernat`.

.. _release-1-0-0-breaking-changes:

Breaking changes
~~~~~~~~~~~~~~~~

- ``release-creator hooks`` now uses a seven-day package cutoff and each hook's configured Python version without
  ``--exclude-newer`` or ``--python-version`` options (:pr:`29`) by :user:`gaborbernat`.

.. _release-1-0-0-security:

Security
~~~~~~~~

- Ignore inherited ``SSL_CERT_DIR`` and ``SSL_CLIENT_CERT`` when resolving hook pins from PyPI (:pr:`29`) by
  :user:`gaborbernat`.
- Reject YAML merge keys in hook definitions so shared dependencies cannot bypass exact pin updates (:pr:`29`) by
  :user:`gaborbernat`.
- Reject duplicate pre-commit YAML keys so effective hook dependencies cannot bypass cooldown and pin updates (:pr:`29`)
  by :user:`gaborbernat`.
- Reject repository-level YAML merge keys before refreshing hook pins, so a merged source cannot hide the hook package
  (:pr:`29`) by :user:`gaborbernat`.

.. _release-0-6-7:

0.6.7 (2026-10-23)
------------------

.. _release-0-6-7-fixed:

Fixed
~~~~~

- Keep a pull request mentioned in prose from inheriting the author credit of a later pull request (:pr:`27`) by
  :user:`gaborbernat`.
- Reject unclosed Markdown code fences and keep indented fences from moving fragment links into code (:pr:`27`) by
  :user:`gaborbernat`.
- Report a missing Git, GitHub CLI, or uv executable by name instead of raising a type error (:pr:`27`) by
  :user:`gaborbernat`.

.. _release-0-6-6:

0.6.6 (2026-10-23)
------------------

.. _release-0-6-6-fixed:

Fixed
~~~~~

- Restore draft changelog pages for repositories with several packages in one Markdown changelog (:pr:`26`) by
  :user:`gaborbernat`.

.. _release-0-6-5:

0.6.5 (2026-10-23)
------------------

.. _release-0-6-5-changes:

Changes
~~~~~~~

- Accept a symlinked plugin archive when its ZIP members match the Marketplace upload (:pr:`25`) by :user:`gaborbernat`.

.. _release-0-6-5-fixed:

Fixed
~~~~~

- Keep fragment links outside trailing Markdown and RST code blocks (:pr:`25`) by :user:`gaborbernat`.
- Keep frozen hook dependency pins attached to the correct hook across YAML styles (:pr:`25`) by :user:`gaborbernat`.
- Reject GitHub release notes whose pull request credits do not match the merged authors (:pr:`25`) by
  :user:`gaborbernat`.

.. _release-0-6-5-removed:

Removed
~~~~~~~

- Stop validating surrounding whitespace in Marketplace plugin IDs and versions and content in ZIP directory entries
  (:pr:`25`) by :user:`gaborbernat`.
- Stop validating GitHub author handle syntax and 40-character Git commit IDs before querying GitHub (:pr:`25`) by
  :user:`gaborbernat`.
- Remove specific missing Git, GitHub CLI, and uv errors from fragment and hook commands; missing executables surface as
  a type error (:pr:`25`) by :user:`gaborbernat`.

.. _release-0-6-4:

0.6.4 (2026-10-23)
------------------

.. _release-0-6-4-changes:

Changes
~~~~~~~

- Remove unused artifact reconciliation, package changelog preview, stable-tag filtering, and numbered-PR fragment
  options (:pr:`22`) by :user:`gaborbernat`.

.. _release-0-6-4-fixed:

Fixed
~~~~~

- Keep hook dependency pins with their own hook when the pre-commit configuration uses block or flow YAML, and resolve
  ranged root requirements (:pr:`22`) by :user:`gaborbernat`.
- Match contributor credits to the final pull request on each generated-notes line, escape RST text in GitHub Markdown,
  and place fragment links outside trailing code blocks (:pr:`22`) by :user:`gaborbernat`.

.. _release-0-6-3:

0.6.3 (2026-10-23)
------------------

.. _release-0-6-3-changes:

Changes
~~~~~~~

- Show Full Changelog as a named link in GitHub Release notes and keep release headings nested in the Sphinx changelog
  (:pr:`21`) by :user:`gaborbernat`.

.. _release-0-6-2:

0.6.2 (2026-10-23)
------------------

.. _release-0-6-2-documentation:

Documentation
~~~~~~~~~~~~~

- Keep the release-creator documentation site and its versioned changelog in reStructuredText (:pr:`19`) by
  :user:`gaborbernat`.

.. _release-0-6-1:

0.6.1 (2026-10-23)
------------------

.. _release-0-6-1-fixed:

Fixed
~~~~~

- Accept Knope changelog sections configured with footers and no changeset types (`#18
  <https://github.com/tox-dev/release-creator/pull/18>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Apply timeouts to the Git and Towncrier commands used for fragment checks and identify the full command when it times
  out (`#18 <https://github.com/tox-dev/release-creator/pull/18>`__) by `@gaborbernat
  <https://github.com/gaborbernat>`__.
- Ignore Towncrier guide and marker files in PR news checks, reject malformed fragment suffixes, and report unsupported
  Towncrier layouts clearly (`#18 <https://github.com/tox-dev/release-creator/pull/18>`__) by `@gaborbernat
  <https://github.com/gaborbernat>`__.
- Reject unknown files and renamed fragments in PR news checks while ignoring editor backup files (`#18
  <https://github.com/tox-dev/release-creator/pull/18>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Resolve fragment pull requests in bounded batches, reject unmerged numbered requests, and credit deleted GitHub
  accounts as ``ghost`` (`#18 <https://github.com/tox-dev/release-creator/pull/18>`__) by `@gaborbernat
  <https://github.com/gaborbernat>`__.

.. _release-0-6-0:

0.6.0 (2026-10-23)
------------------

.. _release-0-6-0-added:

Added
~~~~~

- Link named changelog fragments to squash-merged pull requests and verified human authors using Git history and GitHub
  (`#14 <https://github.com/tox-dev/release-creator/pull/14>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Render reStructuredText changelog entries as Markdown GitHub Release notes while preserving links and author credits
  (`#14 <https://github.com/tox-dev/release-creator/pull/14>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Return verified PyPI file URLs for trusted-publisher attestation after comparing the complete published release with
  local distributions (`#14 <https://github.com/tox-dev/release-creator/pull/14>`__) by `@gaborbernat
  <https://github.com/gaborbernat>`__.

.. _release-0-6-0-changes:

Changes
~~~~~~~

- Read fragment provenance from Git without ``--git`` or ``--commit-map``; use Nab in place of the removed ``locks`` and
  ``build-constraints`` commands (`#14 <https://github.com/tox-dev/release-creator/pull/14>`__) by `@gaborbernat
  <https://github.com/gaborbernat>`__.

.. _release-0-6-0-fixed:

Fixed
~~~~~

- Accept canonical prerelease, postrelease and development tags, and use PEP 440 order when selecting previous releases
  (`#14 <https://github.com/tox-dev/release-creator/pull/14>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Finalize a matching prerelease before applying the next version bump (`#14
  <https://github.com/tox-dev/release-creator/pull/14>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Fix pull request lookup for named changelog fragments during release preparation (`#16
  <https://github.com/tox-dev/release-creator/pull/16>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Preview standard Knope changesets without extra section configuration (`#14
  <https://github.com/tox-dev/release-creator/pull/14>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Read Towncrier defaults and validate fragments from project subdirectories (`#14
  <https://github.com/tox-dev/release-creator/pull/14>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Reject changelog fragments with the wrong file extension before release (`#14
  <https://github.com/tox-dev/release-creator/pull/14>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Reject shallow Git histories when attributing changelog fragments to pull requests (`#14
  <https://github.com/tox-dev/release-creator/pull/14>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Skip non-Python hook dependencies when refreshing pre-commit pins (`#14
  <https://github.com/tox-dev/release-creator/pull/14>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.

.. _release-0-6-0-security:

Security
~~~~~~~~

- Use the final credit in generated GitHub notes when a pull request title contains a forged credit (`#14
  <https://github.com/tox-dev/release-creator/pull/14>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.

.. _release-0-6-0-packaging:

Packaging
~~~~~~~~~

- Include the MIT license file in wheel metadata (`#14 <https://github.com/tox-dev/release-creator/pull/14>`__) by
  `@gaborbernat <https://github.com/gaborbernat>`__.

.. _release-0-5-1:

0.5.1 (2026-10-22)
------------------

.. _release-0-5-1-fixed:

Fixed
~~~~~

- Refresh transitive pre-commit hook dependencies alongside direct pins, including platform-specific packages (`#13
  <https://github.com/tox-dev/release-creator/pull/13>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.

.. _release-0-5-0:

0.5.0 (2026-10-22)
------------------

.. _release-0-5-0-added:

Added
~~~~~

- Add a ``hooks`` command to refresh exact pre-commit ``additional_dependencies`` pins under a release-age cutoff
  without rewriting the rest of the hook configuration (`#11 <https://github.com/tox-dev/release-creator/pull/11>`__) by
  `@gaborbernat <https://github.com/gaborbernat>`__.
- Allow repositories whose numeric Towncrier fragment stems are pull request numbers to preserve the original pull
  request link and verified author during historical backfills (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Calculate versions from ``v``-prefixed release tags and retain that prefix when requested (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Check PyPI filenames and SHA256 digests before retrying a partial upload, stage only missing files, and verify the
  complete published set afterward (`#11 <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat
  <https://github.com/gaborbernat>`__.
- Check a JetBrains Marketplace plugin against its signed ZIP before retrying an upload (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Export one selectable pylock.toml for a project's runtime dependencies, groups, extras, Python range, and platforms
  (`#11 <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Include YAML support in the base package so every command works without an extra (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Include build backend dependencies in the full project lock and select exact, hashed build constraints for the current
  Python and platform (`#11 <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat
  <https://github.com/gaborbernat>`__.
- Link Knope changesets to merged pull requests and repair changelog anchors after release preparation (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Render package and Knope draft fragments beside released history in documentation builds without changing the tracked
  changelog (`#11 <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat
  <https://github.com/gaborbernat>`__.
- Select and validate package-prefixed tags from a mixed repository tag list (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Select hashed build constraints for named operating systems and Python versions, and reject a shared file when their
  dependency selections differ (`#11 <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat
  <https://github.com/gaborbernat>`__.
- Validate changed pull request fragments with the Towncrier configuration (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.

.. _release-0-5-0-fixed:

Fixed
~~~~~

- Convert Sphinx PEP references to links in GitHub Release notes rendered from reStructuredText changelogs (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Convert reStructuredText links in changelog entries to Markdown links in GitHub Release notes (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Credit the merged pull request author for numeric fragments without losing a separate issue link (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Keep GitHub first-contributor credits for human pull requests without a changelog entry (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Keep explicit display text from reStructuredText links in GitHub Release notes (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Keep first-time human contributor credits when GitHub generated notes use a level-three heading (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Keep wrapped reStructuredText author credits attached to their release entry (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Preserve RST field names inside inline code when rendering GitHub release notes (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Preserve each reStructuredText changelog’s configured category heading level when assembling a release (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Preserve named historical author credits when GitHub generated notes omit a deleted account's handle (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Preserve nested lists, code blocks, and warnings when rendering reStructuredText release notes for GitHub (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Reject named changelog fragments without a ``+`` prefix before version selection or release assembly (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Render a credited historical pull request when GitHub generated notes omit it (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Render historical RST release headings that link to a tag but have no date (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Render prerelease and four-part historical version sections in GitHub Release notes (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.

.. _release-0-5-0-documentation:

Documentation
~~~~~~~~~~~~~

- Clarify when to keep ``uv.lock`` alongside the exported ``pylock.toml`` (`#11
  <https://github.com/tox-dev/release-creator/pull/11>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.

.. _release-0-4-1:

0.4.1 (2026-10-19)
------------------

.. _release-0-4-1-fixed:

Fixed
~~~~~

- Render historical release notes for two-part version tags such as 0.2 (`#10
  <https://github.com/tox-dev/release-creator/pull/10>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.

.. _release-0-4-0:

0.4.0 (2026-10-19)
------------------

.. _release-0-4-0-added:

Added
~~~~~

- Render older uncategorized release entries under Other changes without assigning a user-facing category to them (`#9
  <https://github.com/tox-dev/release-creator/pull/9>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.

.. _release-0-3-0:

0.3.0 (2026-10-19)
------------------

.. _release-0-3-0-added:

Added
~~~~~

- Select one package history from a shared Markdown changelog and keep its package-prefixed comparison tags (`#8
  <https://github.com/tox-dev/release-creator/pull/8>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Ship a reStructuredText Towncrier template with stable anchors that follows each changelog's heading style (`#8
  <https://github.com/tox-dev/release-creator/pull/8>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.

.. _release-0-3-0-fixed:

Fixed
~~~~~

- Keep Towncrier's issue links when a release contains numbered fragments alongside named fragments (`#8
  <https://github.com/tox-dev/release-creator/pull/8>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Read bracketed and v-prefixed Markdown release headings when rendering GitHub Release notes (`#8
  <https://github.com/tox-dev/release-creator/pull/8>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Reject uncategorized release items and empty category headings before tagging or publishing a distribution (`#8
  <https://github.com/tox-dev/release-creator/pull/8>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Replace a changelog's existing comparison line when rendering GitHub Release notes, so the body contains one link (`#8
  <https://github.com/tox-dev/release-creator/pull/8>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Select automatic release versions from reStructuredText fragments as well as Markdown fragments (`#8
  <https://github.com/tox-dev/release-creator/pull/8>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.

.. _release-0-2-0:

0.2.0 (2026-10-19)
------------------

.. _release-0-2-0-added:

Added
~~~~~

- Resolve merged pull request authors for changelog credits and verify them against generated GitHub release notes (`#7
  <https://github.com/tox-dev/release-creator/pull/7>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.

.. _release-0-2-0-documentation:

Documentation
~~~~~~~~~~~~~

- Document the feature-release policy for Python support changes (`#5
  <https://github.com/tox-dev/release-creator/pull/5>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
  Additions and drops use feature fragments and select minor releases. New releases will not install on a dropped Python
  version; users who need that version can install an older release.

.. _release-0-1-1:

0.1.1 (2026-10-19)
------------------

.. _release-0-1-1-fixed:

Fixed
~~~~~

- Keep verified new-contributor credits when GitHub links the contributor's first pull request with a URL (`#4
  <https://github.com/tox-dev/release-creator/pull/4>`__) by :user:`gaborbernat`.

.. _release-0-1-0:

0.1.0 (2026-10-19)
------------------

.. _release-0-1-0-added:

Added
~~~~~

- Add post-merge pull request links to named changelog fragments, allowing contributors to write entries before a PR
  number exists (`#1 <https://github.com/tox-dev/release-creator/pull/1>`__) by `@gaborbernat
  <https://github.com/gaborbernat>`__.
- Calculate release versions from pending changelog fragments, with explicit bump and CalVer choices (`#3
  <https://github.com/tox-dev/release-creator/pull/3>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Provide a Towncrier template for Markdown changelogs with stable release and category anchors (`#1
  <https://github.com/tox-dev/release-creator/pull/1>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.
- Render GitHub Release notes from tagged Markdown and reStructuredText changelogs with user-facing categories, human
  mentions, contributor credits, and comparison links (`#1 <https://github.com/tox-dev/release-creator/pull/1>`__) by
  `@gaborbernat <https://github.com/gaborbernat>`__.
- Validate numeric release tags and select the previous tag for GitHub comparison links (`#1
  <https://github.com/tox-dev/release-creator/pull/1>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.

.. _release-0-1-0-fixed:

Fixed
~~~~~

- Format the assembled changelog before release validation so added pull request links and author credits pass ``prek``
  (`#2 <https://github.com/tox-dev/release-creator/pull/2>`__) by `@gaborbernat <https://github.com/gaborbernat>`__.

.. _release-0-1-0-documentation:

Documentation
~~~~~~~~~~~~~

- Document the release flow with a tutorial, command guides, input formats, and a draft changelog in PR documentation
  builds (`#1 <https://github.com/tox-dev/release-creator/pull/1>`__) by `@gaborbernat
  <https://github.com/gaborbernat>`__.
