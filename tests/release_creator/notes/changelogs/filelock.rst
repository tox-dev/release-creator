###########
 Changelog
###########

.. towncrier-draft-entries:: Unreleased

.. towncrier release notes start

.. _release-4-2-4:

********************
 4.2.4 (2026-10-19)
********************

.. _release-4-2-3:

********************
 4.2.3 (2026-10-19)
********************

.. _release-4-2-3-fixed:

Fixed
=====

- Creating a lock on a Python 3.15 interpreter without ``types.LazyImportType`` no longer triggers ``AttributeError`` at
  exit. :pr:`861` - by :user:`gaborbernat`.
- Handle ``EFTYPE`` when a no-follow open refuses a symlink in a soft reader/writer lock's protocol tree, so heartbeat
  reports lost ownership rather than a transient refresh error. :pr:`859` - by :user:`edsonsims`.

.. _release-4-2-2:

********************
 4.2.2 (2026-10-18)
********************
