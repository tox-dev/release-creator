The ``fragments`` linker also drops merge commit authors and pull request authors whose GitHub login is a known AI
assistant (``claude``, ``codex``, ``CommandCodeBot``, ``Copilot``, in any letter case), as ``contributors`` already
does. Before, only AI assistant commit emails were dropped. When no author remains, the linker adds the pull request
link without a credit.
