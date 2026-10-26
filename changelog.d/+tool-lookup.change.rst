``fragments``, ``validate-news`` and ``contributors`` run ``git`` and ``gh`` without looking them up on ``PATH`` first.
A missing executable now fails with the operating system's "No such file or directory" error instead of ``git is
required`` or ``gh is required``.
