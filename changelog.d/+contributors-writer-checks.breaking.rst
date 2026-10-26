``contributors`` no longer rejects a changelog path other than ``.md`` or ``.rst``, ``--package`` with a
reStructuredText changelog, a section that already has a New Contributors subsection, a linked pull request that is not
merged, or a reStructuredText section without a category heading. Unmerged pull requests are skipped, and the
subsection heading falls back to a ``-`` underline.
