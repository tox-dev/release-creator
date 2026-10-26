``validate-news`` and the ``fragments`` linker also detect a ``by`` credit in any letter case after any non-word
character, such as ``(by @alice)`` or ``By @alice``; a ``:user:`` role with any content, such as a display name or a
``[bot]`` login; ``:user:``, ``:pr:`` and ``:pull:`` role names in any letter case; a Markdown profile link whose text
is a code span; and an HTML anchor or HTML block that links a pull request or contains ``#123``. ``validate-news``
rejects them as hand-written attribution, and the linker treats them as already credited or linked.
