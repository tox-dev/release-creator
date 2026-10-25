Reject managed hook dependency pins that select extras, because uv ignores extras in constraints and the
extra's dependencies would install unpinned.
