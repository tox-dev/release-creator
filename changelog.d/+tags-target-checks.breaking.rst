``tags --previous`` prints nothing for a target tag that is not a ``major.minor.patch`` release, or that names another
package than ``--package``, instead of failing. ``tags --next`` with no pending fragments selects a patch release
instead of failing with ``no changelog fragments to release``.
