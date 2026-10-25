# Contributing to release-creator

Run `tox -e dev` to create `.tox/dev`. Run `tox -e 3.15,type,pkg_meta,docs` and
`prek run --all-files --config .pre-commit-config.yaml` before pushing a PR. CI tests Python 3.15 on Linux, macOS, and
Windows.

## Release notes

Add a `changelog.d/+short-name.<type>.rst` fragment for each user-visible change. No issue or PR number is needed when
opening the PR. Use `feature` for additions, `change` for changed behavior, `bugfix` for fixes, or `doc` for
documentation. Other types are `breaking`, `security`, `performance`, `deprecation`, `removal`, and `packaging`. Keep
separate changes in separate fragments.

For Python support changes, use a `feature` fragment for both additions and drops. The note appears under Added and
selects a minor release. New releases will not install on a dropped Python version. Users who need that version can
install an older release. State the exact version change. Reserve `breaking` for changes that require a major release.

Write a complete sentence and credit verified human authors:

```rst
Render GitHub notes without wrapped bullets by :user:`gaborbernat`.
```

For multiple authors, join linked handles with `by x, y and z`. Do not credit reviewers or bots. Bot PRs need no
fragment unless they supply a user-facing change; a bot-only fragment may omit `by`. Apply `skip news` to maintenance
work. This label may be added after opening the PR, and it does not suppress checks for a supplied fragment.

## Release process

The `Prepare release` workflow reads the PR number from each fragment's squash commit, assembles a Towncrier changelog
patch, runs `prek`, then uses the repository-scoped release App to commit and tag on `main`. The tag workflow runs
`prek` again, builds the package, publishes to PyPI through trusted publishing, and creates a GitHub Release using the
tagged `release-creator` source. Set up the App, `release-auth` environment, and PyPI trusted publisher before
dispatching it.

PR documentation builds show the branch's fragments in an `Unreleased` section on the changelog page. Towncrier adds
them to `docs/changelog.rst` only during release preparation.
