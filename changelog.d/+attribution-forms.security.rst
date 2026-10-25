``validate-news`` and the ``fragments`` linker also detect a bare ``by @handle`` credit, a ``:user:`` role anywhere in
the prose, and a bare ``#123`` reference, so ``validate-news`` rejects them as hand-written attribution. The rejection
also covers the body of each changeset checked by ``validate-news --format knope``.
