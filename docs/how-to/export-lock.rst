############################
 Export a full project lock
############################

``locks`` writes a PEP 751 ``pylock.toml`` from uv's resolver. Use it when release tooling and the build backend must be
pinned while keeping the project's other dependency groups, extras, and supported Python versions selectable. The
command resolves runtime dependencies, each group, and each extra separately against PyPI. This matters when a release
tool depends on a published version of the project being locked: uv's workspace export would otherwise omit that
dependency. It resolves ``[build-system].requires`` as a universal ``build`` selection. Python and platform markers
remain in the file.

Run it from the project root:

.. code-block:: bash

    uvx --from release-creator release-creator locks
    uv pip sync --preview-features pylock --python .venv/bin/python --group release pylock.toml

The output contains a ``project-runtime`` group for the package's runtime dependencies, every group from
``[dependency-groups]``, every extra from ``[project.optional-dependencies]``, and a ``build`` group when the project
declares build requirements. No group is selected by default. The command above installs only ``release``. Select
``project-runtime`` when you need the package's runtime dependencies. Each selection has its own resolution, so two
groups can contain different versions of a package. A combined installation can fail even when either group installs
alone; for example, Release Creator's ``project-runtime`` and ``type`` groups select different ``docutils`` versions.
Only combine selections after testing that exact set with ``uv pip sync --group`` on the target Python and platform.

Before building a distribution, select exact build pins and artifact hashes for the current runner. The shared
``github-workflows`` repository ships this script; run it from a checkout of the released version used by your workflow:

.. code-block:: bash

    uv run --no-project --with 'packaging>=26.3' python \
      /path/to/github-workflows/tools/build_constraints.py build-constraints.txt pylock.toml
    uv build --build-constraints build-constraints.txt --require-build-hashes

The output is transient; do not commit it. A missing hash, conflicting selected version, or missing build dependency
stops the build. ``uv build`` verifies the selected artifacts against the lock's hashes. The command evaluates lock
markers for the Python and platform running it, so a universal lock can hold different backend versions for different
Python releases.

When a separate keyless job generates constraints for builders on other operating systems, name the target explicitly.
List every interpreter that will share one constraint file:

.. code-block:: bash

    uv run --no-project --with 'packaging>=26.3' python \
      /path/to/github-workflows/tools/build_constraints.py \
      --target-platform linux_x86_64 \
      --targets '3.11.0:cpython 3.12.0:cpython 3.13.0:cpython 3.14.0:cpython 3.15.0:cpython' \
      linux.txt pylock.toml

The override changes the coupled Python and operating-system marker fields together. It rejects a lock selection that
uses implementation or host-specific machine, release, or version markers because those values cannot be inferred from
the flags. It also rejects different package versions or hashes across the named Python releases. Generate the macOS and
Windows files with the same version list and their respective ``--target-platform`` values. Run the command on each
target runner if the lock uses unsupported markers.

Some backends request additional dependencies during a build. If the backend's hook has a known conditional requirement,
add it during lock generation. For example, meson-python can request ``patchelf`` on Linux:

.. code-block:: bash

    release-creator locks --build-requirement 'patchelf>=0.11.0; sys_platform == "linux"'

``--build-requirement`` can be repeated. An undeclared dynamic dependency fails the hashed build until the lock includes
it. Keep this supplement close to the repository's release workflow so its reason stays visible.

The command leaves an existing ``uv.lock`` untouched. Commit ``pylock.toml``. Use ``--keep-uv-lock`` only when the
project also uses uv's native lock for its own build. It refreshes both files under the same seven-day cutoff, then
normalizes the native lock so an ordinary ``uv lock --check`` agrees. The check compares native artifacts with the
cooled project lock, including their URLs, hashes, and upload times. The native lock's test, type, and docs entries are
cooled too. Run those CI jobs with fresh resolution outside the lock when they need to catch upstream dependency
changes. A failed resolution leaves the previous ``pylock.toml`` intact and prints uv's error. For a library that
supports Python 3.11 but uses Sphinx 9 in its ``docs`` group, declare that group's Python minimum under
``[tool.uv.dependency-groups]``. uv cannot infer that the group is optional from the library's runtime
``requires-python`` alone. The global seven-day cutoff applies to every selection, including build requirements. If a
project raises one package's minimum above that cutoff, pass ``--exclude-newer-package NAME=UTC_DATE`` for that package
during the refresh. Set the package cutoff after the latest file upload for the reviewed version: a cutoff within the
upload window can keep one wheel and omit the others. Review each exception and run the lock's supported Python and
platform selections in the lock refresh pull request.

Run ``release-creator locks --check`` in pull request checks to verify that the committed lock still represents the
project's groups, extras, and dependencies. It resolves against the committed lock's creation date, so an unrelated pull
request does not fail merely because a newer dependency became available after the weekly refresh.

The command reads ``[project].requires-python``. For a tool-only ``pyproject.toml`` without ``[project]``, pass
``--tool-python '>=3.15'`` to describe its release-tool environment. It reserves the ``project-runtime`` group name for
the lock's runtime selection. An existing ``build`` group is combined with the backend requirements.

At a uv workspace root, the command includes every listed member and combines their groups and extras. Members must
declare the same ``requires-python`` range; a mismatch fails before writing a lock. The root can omit ``[project]`` when
its members provide that range.

Release Creator retains its ``[tool.nab]`` policy while its tagged release workflow uses an older shared workflow
version. The exporter writes compatible ``[tool.nab]`` creation metadata alongside its own metadata so that release can
validate the full lock before the shared workflow is upgraded. The lock still covers every declared selection.
