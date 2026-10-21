############################
 Export a full project lock
############################

``locks`` writes a PEP 751 ``pylock.toml`` from uv's project resolution. Use it when release tooling and the build
backend must be pinned without losing the project's other dependency groups, extras, or supported Python versions. The
command runs ``uv lock --upgrade`` and then exports the runtime dependencies, each group, and each extra separately. It
resolves ``[build-system].requires`` as a universal ``build`` selection. Python and platform markers remain in the
resulting file.

Run it from the project root:

.. code-block:: bash

    uvx --from release-creator release-creator locks
    uv pip sync --preview-features pylock --python .venv/bin/python --group release pylock.toml

The output contains a ``project-runtime`` group for the package's runtime dependencies, every group from
``[dependency-groups]``, every extra from ``[project.optional-dependencies]``, and a ``build`` group when the project
declares build requirements. No group is selected by default. The command above installs only ``release``. Select
``project-runtime`` when you need the package's runtime dependencies, or combine it with another group or extra when
that environment needs both.

Before building a distribution, select exact build pins and artifact hashes for the current runner:

.. code-block:: bash

    release-creator build-constraints --lock pylock.toml --output build-constraints.txt
    uv build --build-constraints build-constraints.txt --require-build-hashes

The output is transient; do not commit it. A missing hash, conflicting selected version, or missing build dependency
stops the build. ``uv build`` verifies the selected artifacts against the lock's hashes. The command evaluates lock
markers for the Python and platform running it, so a universal lock can hold different backend versions for different
Python releases.

Some backends request additional dependencies during a build. If the backend's hook has a known conditional requirement,
add it during lock generation. For example, meson-python can request ``patchelf`` on Linux:

.. code-block:: bash

    release-creator locks --build-requirement 'patchelf>=0.11.0; sys_platform == "linux"'

``--build-requirement`` can be repeated. An undeclared dynamic dependency fails the hashed build until the lock includes
it. Keep this supplement close to the repository's release workflow so its reason stays visible.

The command updates an existing ``uv.lock``. If none exists, it uses a temporary one and removes it after export. Commit
``pylock.toml``. Keep ``uv.lock`` untracked unless the project also uses that lock for its own build. A failed uv
resolution leaves the previous ``pylock.toml`` intact and prints uv's error. For a library that supports Python 3.11 but
uses Sphinx 9 in its ``docs`` group, declare that group's Python minimum under ``[tool.uv.dependency-groups]``. uv
cannot infer that the group is optional from the library's runtime ``requires-python`` alone. ``UV_EXCLUDE_NEWER``
applies to both the project and build resolution; its cutoff must be compatible with the declared lower bounds. If a
project raises one package's minimum above the global cutoff, pass ``--exclude-newer-package NAME=UTC_DATE`` for that
package during the refresh. The global cutoff still applies to every other package. Repeat the option when several newly
required minima need an exception; review each exception in the lock refresh pull request.

The command reads ``[project].requires-python``. For a tool-only ``pyproject.toml`` without ``[project]``, pass
``--tool-python '>=3.15'`` to describe its release-tool environment. It reserves the ``project-runtime`` group name for
the lock's runtime selection and ``build`` for the build selection.

At a uv workspace root, the command includes every listed member and combines their groups and extras. Members must
declare the same ``requires-python`` range; a mismatch fails before writing a lock. The root can omit ``[project]`` when
its members provide that range.
