Remove the ``locks`` options ``--project``, ``--output``, ``--tool-python``, ``--build-requirement`` and
``--exclude-newer-package``, which no caller used. The command reads ``pyproject.toml`` and writes ``pylock.toml`` in the
current directory. Declare dynamic build requirements in a ``build`` dependency group and package cutoffs in
``[tool.release-creator.locks.exclude-newer-package]``.
