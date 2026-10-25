Resolve each ``release-*`` group under the pins of ``project-runtime`` and of the ``release-*`` groups before it, so a
lock whose release selections cannot be installed together fails when it is refreshed rather than in the release job.
