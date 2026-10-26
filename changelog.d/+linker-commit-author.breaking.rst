The ``fragments`` linker no longer fails for a shallow checkout, a fragment without an introducing commit, or a commit
without exactly one squash-merged pull request. A fragment whose commit has no squash-merged pull request gets no pull
request link and credits the commit author after Git's mailmap, as the GitHub login for a GitHub noreply email and
otherwise as the author name, dropping AI assistants and the ``[bot]`` suffix as pull request credits do. With several
squash-merged pull requests the first is used. In a shallow checkout, and for a fragment without a commit or with an AI
assistant author, the fragment stays unchanged. ``add_pull_request_links`` takes a new required ``commits`` argument,
and ``fragment_commits_from_git`` returns ``FragmentCommit`` values.
