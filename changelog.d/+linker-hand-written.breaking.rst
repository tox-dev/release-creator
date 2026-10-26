The ``fragments`` linker no longer re-checks fragments that ``validate-news`` already checked on the pull request. It
links a structured fragment, a named fragment that already links its pull request, a name without the ``+`` prefix,
and a fragment with several hand-written credits instead of failing. A hand-written credit stays as written, and the
linker appends the pull request link and computed credit after it. ``tags --next`` treats a name without the ``+``
prefix as a patch change. ``fragment_number`` is removed.
