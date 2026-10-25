Record the resolving uv version as ``uv-version`` in ``pylock.toml`` and make ``locks --check`` report a different uv
before comparing the lock. Stop writing the ``[tool.nab]`` creation stamp. Existing locks must be refreshed.
