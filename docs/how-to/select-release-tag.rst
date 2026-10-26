##############################
 Select a numeric release tag
##############################

``tags`` calculates a version from pending changelog fragments and existing tags. It also finds the tag for the GitHub
comparison link. It reads tag names from standard input and never creates or moves a tag.

Calculate the next version
==========================

Use ``--next auto`` in a release workflow. ``--directory`` defaults to ``changelog.d``:

.. code-block:: bash

    git tag --list | uvx --from release-creator release-creator tags --next auto

An ``*.breaking.md`` or ``*.removal.md`` fragment requests a major bump, since removing an interface breaks its callers.
Otherwise, an ``*.feature.md`` fragment requests a minor bump; other fragments request a patch bump. If several kinds
are present, the largest bump wins. From ``1.2.3``, a feature produces ``1.3.0`` and a bug fix alone produces ``1.2.4``.
With no numeric tags, a feature produces ``0.1.0``.

For repositories with ``v``-prefixed release tags, add ``--prefix v``. Existing ``v1.2.3`` and ``1.2.3`` tags both count
when selecting the next version; the option controls the new tag's spelling:

.. code-block:: bash

    git tag --list | uvx --from release-creator release-creator tags --next auto --prefix v

In a repository that tags several packages, pass ``--package`` and the complete tag list. The command selects only that
package's tags, reads fragments from ``changelog.d/<package>`` by default, and prints the full package tag:

.. code-block:: bash

    git tag --list | release-creator tags --next auto --package pyproject-fmt

With ``pyproject-fmt/2.30.3`` already tagged and a pending bug fix, this prints ``pyproject-fmt/2.30.4``. Other
packages' tags do not affect the version.

For tox-dev libraries, both adding and dropping a supported Python version use a ``feature`` fragment, such as
``+drop-python-3-9.feature.md``. The note appears under Added and automatic version selection makes a minor release. New
releases will not install on a dropped Python version. Users who need that version can install an older release. State
the exact Python version in the fragment. Reserve ``*.breaking.md`` for changes that require a major bump.

Choose ``--next major``, ``minor``, or ``patch`` to override that classification.

Find the comparison base
========================

Suppose ``git tag --list`` prints ``1.2.1``, ``1.2.2``, and ``docs-preview``. For ``1.2.3``, run:

.. code-block:: bash

    git tag --list | uvx --from release-creator release-creator tags 1.2.3 --previous

The output is ``1.2.2``. Pass it to ``notes --previous 1.2.2`` to link the changes since that release. For a first
numeric release, ``--previous`` prints nothing; ``notes`` then links to the commits at the new tag.

For package tags, add ``--package pyproject-fmt`` and pass either ``2.30.4`` or ``pyproject-fmt/2.30.4`` as the target.
The output keeps the package prefix, for example ``pyproject-fmt/2.30.3``, ready for ``notes --previous``.

Rules and failure cases
=======================

Release tags have three numeric components, ``major.minor.patch`` or ``year.month.patch``, with an optional ``v``
prefix. Prerelease, postrelease, and development suffixes are accepted, and ``1.2.3`` is newer than ``1.2.3rc1``.
Existing tags with other forms, such as ``docs-preview`` or a floating ``v1`` tag, do not take part in the comparison.
Numeric components are compared as numbers, so ``v1.2.10`` follows ``1.2.9``. ``--previous`` selects the greatest
numeric tag below the proposed one, retains its prefix, and ignores input order. A proposed tag of another form has no
predecessor, so the command prints nothing. Choose one option at a time; they answer different questions.
