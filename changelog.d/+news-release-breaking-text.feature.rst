``validate-news`` rejects a fragment or Knope changeset that contains the private-use character U+E000 or an unclosed
Markdown code fence, and a reStructuredText fragment with a parser warning or error, such as an unknown directive or
role, an empty ``code-block``, or an ``include``. These were caught only when preparing or publishing the release;
``fragments`` and ``notes`` no longer reject them.
