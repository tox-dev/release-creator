The ``fragments`` linker asks GitHub about at most 40 fragment commits per GraphQL query. A batch of 50 or more
exceeded GitHub's node limit and failed with ``MAX_NODE_LIMIT_EXCEEDED``, so release preparation with many fragments
aborted.
