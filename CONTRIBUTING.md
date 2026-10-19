# Contributing to release-creator

Run `tox -e dev` to create `.tox/dev`. Run `tox -e 3.15,type,pkg_meta,docs` and `prek run --all-files` before pushing a
PR. CI tests Python 3.15 on Linux, macOS, and Windows.

## Release notes

Add a `changelog.d/+short-name.<type>.md` fragment for each user-visible change. No issue or PR number is needed when
opening the PR. Use `feature` for additions, `change` for changed behavior, `bugfix` for fixes, or `doc` for
documentation. Other types are `breaking`, `security`, `performance`, `deprecation`, `removal`, and `packaging`. Keep
separate changes in separate fragments.

For both additions and drops in supported Python versions, use a `feature` fragment. The automatic selector makes a
minor release, and users who need a dropped runtime can continue using earlier releases. State the exact version change.
This rule takes precedence over the `breaking` type for Python runtime support changes.

Write a complete sentence and credit verified human authors:

```markdown
Render GitHub notes without wrapped bullets by [@gaborbernat](https://github.com/gaborbernat).
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
them to `docs/changelog.md` only during release preparation.
