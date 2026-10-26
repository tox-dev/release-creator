``validate-news`` rejects Towncrier ``section`` entries and a ``package`` without an explicit ``directory`` only when
the pull request changes the ``[tool.towncrier]`` table or ``towncrier.toml`` compared with ``--base``.
