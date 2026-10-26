``fragments``, ``notes``, ``contributors``, ``tags`` and the changelog preview no longer reject a malformed
``--repository``, ``--tag``, ``--previous`` or ``--package`` value, a ``notes --package`` that does not match the tag's
package, or a non-HTTPS ``--artifact-url``. They use the value as given.
