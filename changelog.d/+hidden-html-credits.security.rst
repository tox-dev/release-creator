Check credits and links inside inline HTML elements such as ``<code>`` in GitHub release notes, since GitHub renders
them. Reject release entries and fragments with ``<details>``, ``<summary>``, or an HTML comment left open across
blocks, which could hide the real author behind a false credit.
