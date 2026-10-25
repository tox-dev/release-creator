###########
 Changelog
###########

.. towncrier release notes start

.. _release-1-18-4:

`1.18.4 <https://github.com/pypa/pipx/tree/1.18.4>`_ - 2026-10-18
=================================================================

.. _release-1-18-4-fixed:

Fixed
-----

- `pipx reset` now cancels instead of crashing when the confirmation prompt reads EOF (Ctrl-D on POSIX, Ctrl-Z then
  Enter on Windows). (:pr:`2160`) by :user:`XXXXXQ-0206` and :user:`gaborbernat`

.. _release-1-18-3:

`1.18.3 <https://github.com/pypa/pipx/tree/1.18.3>`_ - 2026-10-17
=================================================================

.. _release-1-18-3-fixed:

Fixed
-----

- Allow selecting dependencies that ship only shell completions. (:pr:`2157`) by :user:`AryanRG` and :user:`gaborbernat`
