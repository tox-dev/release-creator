``notes`` and ``contributors`` use the first matching version section, and the first ``## <package>`` section, instead
of requiring exactly one; a missing section now raises ``StopIteration``. ``notes`` renders an unknown category under
its own name, passes Markdown text outside a category or item through unchanged, keeps empty Markdown categories, and
renders reStructuredText blocks outside a category or item, and unsupported nested blocks such as a nested
``.. warning::``, as plain text instead of failing.
