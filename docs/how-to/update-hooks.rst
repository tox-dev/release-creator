##############################
Update hook dependency pins
##############################

``prek update --freeze`` moves pre-commit hook revisions to commit SHAs. It does not update packages installed through
``additional_dependencies``. Use ``release-creator hooks`` in the same weekly change to refresh exact package pins:

.. code-block:: bash

   prek update --freeze --cooldown-days 7
   release-creator hooks \
     --config .pre-commit-config.yaml \
     --exclude-newer "$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)" \
     --python-version 3.15
   prek run --all-files

The command reads ``.pre-commit-config.yaml`` and resolves all exact pins in ``additional_dependencies`` in one uv
request. For example, ``mdformat-gfm==1.0.0`` can become ``mdformat-gfm==1.1.0``. A range such as
``mdformat-gfm>=1`` stays as written. YAML comments, quoting, and hook configuration stay in place. The Python version
must match the hooks' intended interpreter, and the cutoff keeps newly published packages out of the weekly update.

If uv cannot resolve every pinned package, the command fails without changing the file. Review the patch and run
``prek`` before opening the update PR. The command does not update hook revisions, project requirements, or
``pylock.toml``; the weekly workflow handles those separately.
