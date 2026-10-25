# release-creator

![release-creator logo](docs/_static/logo-128.png)

[![PyPI](https://img.shields.io/pypi/v/release-creator?style=flat-square)](https://pypi.org/project/release-creator/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/release-creator.svg)][pypi]
[![check](https://github.com/tox-dev/release-creator/actions/workflows/check.yaml/badge.svg)][checks]

Release preparation tools for Python projects that keep a Towncrier changelog. The
[documentation](https://release-creator.readthedocs.io/) has a tutorial, how-to guides, a generated command reference,
and an explanation of where each part of a release comes from.

## Commands

`tags` calculates the next version from pending fragments and checks a proposed tag against existing ones:

```bash
git tag --list | uvx --from 'release-creator' release-creator tags --next auto
git tag --list | uvx --from 'release-creator' release-creator tags 1.2.3 --require-newer
```

`notes` prints the section of one release from a Markdown or reStructuredText changelog, without its heading and in the
changelog's own format. Pass it to `gh release create --notes-file` together with `--generate-notes`, which adds the
pull request list and credits:

```bash
uvx --from 'release-creator' release-creator notes --changelog CHANGELOG.md --tag 1.2.3 > section.md
gh release create 1.2.3 --verify-tag --notes-file section.md --generate-notes --notes-start-tag 1.2.2
```

`hooks` pins the complete dependency closure of each Python pre-commit hook under a seven-day cooldown, and
`hooks --check` verifies the pins on a pull request. `validate-fragment-deletions` checks that a release patch deletes
only consumed fragments. `marketplace` compares a signed JetBrains plugin with the published version.

For automation, replace `release-creator` after `--from` with a tested `release-creator==VERSION`.

## Development and releases

See [contributing](CONTRIBUTING.md) for the fragment format and release process. Run `tox -e 3.15,type,pkg_meta,docs`
and `prek run --all-files --config .pre-commit-config.yaml` before a PR.

[checks]: https://github.com/tox-dev/release-creator/actions/workflows/check.yaml
[pypi]: https://pypi.org/project/release-creator/
