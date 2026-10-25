Reject pre-commit configurations where two hook repositories share a hook list or hook through a YAML alias, which
resolved only one repository's dependency closure, and dependency lists that reuse an anchored entry, which received
managed pins at the anchor.
