``validate-news`` no longer rejects an empty ``--base``, a Towncrier changelog filename other than ``.md`` or ``.rst``,
a ``pyproject.toml`` without ``[tool.towncrier]``, or a ``knope.toml`` without exactly one package. ``validate-news``
and ``changelog`` no longer check the shape of Knope ``extra_changelog_sections``. With several ``[packages.<name>]``
tables, the first one is used.
