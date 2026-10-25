#############################
 Update hook dependency pins
#############################

``prek update --freeze`` moves pre-commit hook revisions to commit SHAs. Use ``release-creator hooks`` in the same
weekly change to pin packages declared by Python hook repositories and packages in ``additional_dependencies``:

.. code-block:: bash

    prek update --freeze --cooldown-days 7
    release-creator hooks
    prek run --all-files --config .pre-commit-config.yaml

On a hook update PR, ``release-creator hooks --check`` checks the proposed pins without changing the file. It resolves
the frozen hook revision and direct dependencies at their proposed versions, uses managed pins as constraints, and
requires the managed pins to match the complete dependency closure. A removed dependency can lose its managed pin;
removing a pin that is still needed fails the check. The same PyPI-only resolution and seven-day cutoff apply. Use
``--minimum-days N`` on both commands when the repository requires a longer package cooldown; the minimum is seven.

The command checks out each external hook repository at its frozen commit and reads ``.pre-commit-hooks.yaml``. For
selected Python hooks, it resolves the repository package with all ``additional_dependencies`` and adds the pinned
closure to that hook's ``additional_dependencies``. It also resolves dependencies in local hooks. Conditional
dependencies remain conditional, so a Windows-only package does not install on Linux. A hook whose language is not
Python, in the configuration or in the hook repository's manifest, cannot declare ``additional_dependencies``, because
nothing would pin or cool them.

Generated pins have a ``# release-creator managed`` marker. The next update replaces them. Direct pins retain their
comments and version ranges; ranges and unpinned requirements gain a separate exact pin. A flow-style list becomes a
block list when the closure adds packages. Resolution uses each hook's ``language_version``, then its manifest default,
then the top-level ``default_language_version``; otherwise it targets Python 3.15. It excludes packages released in the
last seven days and ignores uv config files, source overrides, and environment settings that could change the index,
resolver, or TLS trust. It resolves packages from PyPI. An alias inside ``additional_dependencies`` is rejected because
changing the anchor could also change an unrelated hook field. A hook list or hook that two repositories share through
an alias is rejected because its dependencies would be resolved against only one repository. YAML merge keys at the
configuration root and in hook and repository definitions are rejected because they can hide a hook's dependencies or
source from the updater. Managed pins cannot select extras, since uv ignores extras in constraints. A free-threaded
``language_version`` such as ``python3.14t`` resolves like ``python3.14``.

If uv cannot resolve every pinned package, the command fails without changing the file. Review the patch and run
``prek`` with ``--config .pre-commit-config.yaml`` before opening the update PR, so it runs no other configuration file.
The command does not update hook revisions, project requirements, or ``pylock.toml``; the weekly workflow handles those
separately.
