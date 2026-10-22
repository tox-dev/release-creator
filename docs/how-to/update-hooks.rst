#############################
 Update hook dependency pins
#############################

``prek update --freeze`` moves pre-commit hook revisions to commit SHAs. It does not update packages installed through
``additional_dependencies``. Use ``release-creator hooks`` in the same weekly change to refresh exact package pins:

.. code-block:: bash

    prek update --freeze --cooldown-days 7
    release-creator hooks \
      --config .pre-commit-config.yaml \
      --exclude-newer "$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)" \
      --python-version 3.15
    prek run --all-files

The command resolves each hook's exact ``additional_dependencies`` and their transitive packages separately. It pins the
full closure across platforms, including conditional dependencies such as Windows-only packages. Each added pin has an
inline ``# release-creator managed`` marker so a later update can replace or remove it. Direct pins retain their
spelling and comments; a flow-style list becomes a block list when the closure adds packages. A range such as
``mdformat-gfm>=1`` stays as written and is not a resolution root. Use the Python version that the hooks run with; the
cutoff excludes newly published packages.

If uv cannot resolve every pinned package, the command fails without changing the file. Review the patch and run
``prek`` before opening the update PR. The command does not update hook revisions, project requirements, or
``pylock.toml``; the weekly workflow handles those separately.
