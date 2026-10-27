# release-creator

![release-creator logo](docs/_static/logo-128.png)

[![PyPI](https://img.shields.io/pypi/v/release-creator?style=flat-square)](https://pypi.org/project/release-creator/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/release-creator.svg)][pypi]
[![check](https://github.com/tox-dev/release-creator/actions/workflows/check.yaml/badge.svg)][checks]

Release preparation tools for Python projects. The `notes` command renders a tagged changelog section for a GitHub
Release. Other release tasks can use separate commands.

The [documentation](https://release-creator.readthedocs.io/) has a tutorial, how-to guides, a generated command
reference, and an explanation of the changelog format.

## Render GitHub Release notes

Run the current release from PyPI:

```bash
uvx --from 'release-creator' release-creator notes \
  --changelog docs/changelog.md \
  --tag 1.2.3 \
  --repository tox-dev/example \
  --previous 1.2.2 \
  --artifact-url https://pypi.org/project/example/1.2.3/ > release-notes.md
```

For automation, replace `release-creator` after `--from` with a tested `release-creator==VERSION`. The command reads the
tagged section, maps `Added` to `Features` and `Fixed` to `Bug fixes`, changes linked author handles to GitHub mentions,
and leaves bullets unwrapped. It keeps stable category anchors, omits empty categories when they are absent from the
source, and adds artifact and comparison links. Use `--artifact-label` for an ecosystem other than PyPI, repeat both
options for each published package, and omit `--artifact-url` when there is no external artifact.

The command also accepts a `.rst` changelog with the same category names. It links `:issue:` roles to issues and `:pr:`
or `:pull:` roles to pull requests:

```bash
uvx --from 'release-creator' release-creator notes \
  --changelog docs/changelog.rst \
  --tag 1.2.3 \
  --repository tox-dev/example \
  --previous 1.2.2 \
  --artifact-url https://pypi.org/project/example/1.2.3/ > release-notes.md
```

The changelog is the source of truth. The command does not infer changes from commits or generate an author list.
Fragments carry no hand-written credits or PR references; `validate-news` rejects them. The GitHub Release body contains
only the tagged changelog section.

Named Towncrier fragments need no issue or PR number. Before Towncrier builds the changelog, run
`release-creator fragments --repository owner/repo`. The command reads the commits that introduced pending fragments,
asks GitHub which squash-merged pull request owns each commit, and adds its PR link and a credit computed from the merge
commit: the PR author first, then every other author and co-author. AI assistant identities are dropped, and bots are
credited only when they are the only author. `gh` needs read access to the repository. A fragment whose introducing
commit has no squash-merged PR, as after a merge commit or rebase merge, gets no PR link and credits the commit author
by the same rules. In a shallow checkout the linker leaves every fragment unchanged.

The `tags` command calculates a version from pending fragments and selects the preceding tag for GitHub comparisons:

```bash
git tag --list | uvx --from 'release-creator' release-creator tags --next auto
git tag --list | uvx --from 'release-creator' release-creator tags 1.2.3 --previous
```

## Development and releases

See [contributing](CONTRIBUTING.md) for the fragment format and release process. The package uses the same `notes`
command for its own GitHub Releases. Run `tox -e 3.15,type,pkg_meta,docs` and
`prek run --all-files --config .pre-commit-config.yaml` before a PR.

[checks]: https://github.com/tox-dev/release-creator/actions/workflows/check.yaml
[pypi]: https://pypi.org/project/release-creator/
