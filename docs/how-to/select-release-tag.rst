############################
Select a numeric release tag
############################

``tags`` calculates a version from pending changelog fragments and existing tags. It also checks a proposed version
and finds the tag for the GitHub comparison link. It reads tag names from standard input and never creates or moves
a tag.

Calculate the next version
==========================

Use ``--next auto`` in a release workflow. ``--directory`` defaults to ``changelog.d``:

.. code-block:: bash

   git tag --list | uvx --from release-creator release-creator tags --next auto

An ``*.breaking.md`` fragment requests a major bump. Otherwise, an ``*.feature.md`` or ``*.breaking.minor.md`` fragment
requests a minor bump; other fragments request a patch bump. If several kinds are present, the largest bump wins. From
``1.2.3``, a feature produces ``1.3.0`` and a bug fix alone produces ``1.2.4``. With no numeric tags, a feature
produces ``0.1.0``.

For tox-dev libraries, Python support additions use a ``feature`` fragment. A support drop uses
``+drop-python-3-9.breaking.minor.md``: Towncrier categorizes it as ``Breaking changes``, while automatic version
selection makes a minor release because users can continue using earlier releases. State the exact Python version in
the fragment. Use ``*.breaking.md`` for other changes that require a major bump.

Choose ``--next major``, ``minor``, or ``patch`` to override that classification. ``--next calver`` uses
``year.month.patch``: the first October 2026 release is ``2026.10.0``, and the next is ``2026.10.1``. CalVer uses
the runner's current date. Every choice requires at least one fragment and must produce a version newer than all
existing numeric tags.

Check a proposed version
========================

Suppose ``git tag --list`` prints ``1.2.1``, ``1.2.2``, and ``docs-preview``. Before preparing ``1.2.3``, run:

.. code-block:: bash

   git tag --list | uvx --from release-creator release-creator tags 1.2.3 --require-newer

A successful check prints nothing and exits with status zero. If ``1.2.3`` or a newer numeric tag already exists,
the command fails. This prevents release preparation from reusing a version or publishing an older one. A name such
as ``1.2.3rc1`` also fails: this command accepts exactly three numeric components.

Find the comparison base
========================

For the same tag list, run:

.. code-block:: bash

   git tag --list | uvx --from release-creator release-creator tags 1.2.3 --previous

The output is ``1.2.2``. Pass it to ``notes --previous 1.2.2`` to link the changes since that release. For a first
numeric release, ``--previous`` prints nothing; ``notes`` then links to the commits at the new tag.

Rules and failure cases
=======================

The proposed tag must have three numeric components, ``major.minor.patch`` or ``year.month.patch``. Existing tags
with other forms, such as ``docs-preview`` or ``v1.2.2``, do not take part in the comparison. Numeric components
are compared as numbers, so ``1.2.10`` follows ``1.2.9``. ``--previous`` selects the greatest numeric tag below
the proposed one, regardless of input order.

Without ``--previous`` or ``--require-newer``, the command only validates the proposed tag's format and does not read
standard input. Choose one option at a time; they answer different questions.
