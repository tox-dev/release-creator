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
removing a pin that is still needed fails the check. Use ``--minimum-days N`` on both commands when the repository
requires a longer package cooldown; the minimum is seven.

What the command pins
=====================

The command checks out each external hook repository at its frozen commit and reads ``.pre-commit-hooks.yaml``. For
Python hooks, it resolves the repository package with all ``additional_dependencies`` and adds the pinned closure to
that hook's ``additional_dependencies``. It also resolves dependencies in local hooks. Conditional dependencies of the
closure stay conditional, so a Windows-only package does not install on Linux.

Generated pins have a ``# release-creator managed`` marker. The next update replaces them. Direct pins keep their
comments and version ranges; ranges and unpinned requirements gain a separate exact pin. Resolution uses each hook's
``language_version``, then its manifest default, then the top-level ``default_language_version``; otherwise it targets
Python 3.15. A free-threaded ``language_version`` such as ``python3.14t`` resolves like ``python3.14``. It excludes
packages released in the last seven days, resolves from PyPI, and ignores uv config files, source overrides, and
environment settings that could change the index, resolver, or TLS trust.

What the command rejects
========================

Each rejection closes a way to install something the cooldown did not check:

- A dependency that starts with ``-``, contains ``@``, ``://``, ``file:``, ``/`` or ``\``, starts with ``.`` or ``~``,
  or names an archive such as ``black.whl``. uv would read it as an option, a URL, or a path rather than an index
  package. This also applies to defaults in a hook repository's manifest.
- ``UV_*``, ``PIP_*`` and ``PYTHON*`` keys in ``default_env`` or in a hook's ``env``, since they can point the installer
  at another index or change what the hook imports.
- ``additional_dependencies`` on a hook whose language is not Python, in the configuration or in the hook repository's
  manifest, because nothing would pin or cool them.
- An environment marker on a direct dependency; list the package unconditionally instead.
- A managed pin that is not exact or selects extras, since uv ignores extras in constraints.
- YAML aliases, merge keys, and duplicate keys anywhere in the file, since they can hide what a hook installs.
- An external repository whose ``rev`` is not a full commit SHA.

A flow-style list such as ``[black==26.1.0]`` keeps its form while it holds only exact pins. Once the closure needs
managed pins, the command asks for a block list instead of rewriting the line.

If uv cannot resolve every pinned package, the command fails without changing the file. Review the patch and run
``prek`` with ``--config .pre-commit-config.yaml`` before opening the update PR, so it runs no other configuration file.
The command does not update hook revisions, project requirements, or ``pylock.toml``.
