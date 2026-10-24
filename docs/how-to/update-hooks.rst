#############################
 Update hook dependency pins
#############################

``prek update --freeze`` moves pre-commit hook revisions to commit SHAs. Use ``release-creator hooks`` in the same
weekly change to pin packages declared by Python hook repositories and packages in ``additional_dependencies``:

.. code-block:: bash

    prek update --freeze --cooldown-days 7
    release-creator hooks
    prek run --all-files

The command checks out each external hook repository at its frozen commit and reads ``.pre-commit-hooks.yaml``. For
selected Python hooks, it resolves the repository package with all ``additional_dependencies`` and adds the pinned
closure to that hook's ``additional_dependencies``. It also resolves dependencies in local hooks. Conditional
dependencies remain conditional, so a Windows-only package does not install on Linux. Non-Python hooks are unchanged.

Generated pins have a ``# release-creator managed`` marker. The next update replaces them. Direct pins retain their
comments and version ranges; ranges and unpinned requirements gain a separate exact pin. A flow-style list becomes a
block list when the closure adds packages. Resolution uses each hook's ``language_version`` or the top-level
``default_language_version``; otherwise it targets Python 3.15. It excludes packages released in the last seven days and
ignores uv config files, source overrides, and uv and pip environment settings that could change the index or resolver.
It resolves packages from PyPI. An alias that shares an edited value is rejected because changing the anchor could also
change an unrelated hook field. YAML merge keys in hook definitions are rejected because they can hide dependencies from
the updater.

If uv cannot resolve every pinned package, the command fails without changing the file. Review the patch and run
``prek`` before opening the update PR. The command does not update hook revisions, project requirements, or
``pylock.toml``; the weekly workflow handles those separately.
