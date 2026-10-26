"""Read the pull requests associated with fragment commits."""

# ruff: file-ignore[lazy-import-immediately-resolved]  # The shared regex and dataclass decorators resolve during module load.
from __future__ import annotations

lazy import json
lazy import re
lazy from dataclasses import dataclass
lazy from typing import Final

lazy from release_creator.process import required_executable, run_text

_RE_AI_ASSISTANT_EMAIL: Final = re.compile(
    r"""
    @anthropic\.com$                                # Claude
    | @openai\.com$                                 # Codex
    | @commandcode\.ai$                             # Command Code
    | @zo\.computer$                                # Zo
    | ^\d+\+Copilot@users\.noreply\.github\.com$     # GitHub Copilot
    """,
    re.VERBOSE | re.IGNORECASE,
)
AI_ASSISTANT_LOGINS: Final = frozenset(
    login.casefold()
    for login in (
        "claude",
        "codex",
        "CommandCodeBot",
        "Copilot",
    )
)


def fragment_pull_requests(repository: str, commits: dict[str, str]) -> dict[str, PullRequest]:
    """Resolve each fragment through GitHub's commit-to-pull-request API.

    A missing GitHub CLI executable raises :exc:`FileNotFoundError`.

    :param repository: GitHub owner and repository.
    :param commits: Fragment names mapped to introducing commit hashes.
    :returns: Fragment names mapped to the merged pull request and its author.
    """
    gh = required_executable("gh")
    by_commit = _pulls(gh, repository, list(dict.fromkeys(commits.values())))
    return {name: by_commit[sha] for name, sha in commits.items()}


def _pulls(gh: str, repository: str, shas: list[str]) -> dict[str, PullRequest]:
    if not shas:
        return {}
    owner, name = repository.split("/", 1)
    pulls: dict[str, PullRequest] = {}
    aliases = [
        (
            f"c{index}",
            sha,
            (
                f'c{index}: object(oid: "{sha}") {{ ... on Commit {{ associatedPullRequests(first: 100) '
                "{ nodes { number mergedAt author { login __typename } mergeCommit { oid authors(first: 100) "
                "{ nodes { name email user { login __typename } } } } } } } }"
            ),
        )
        for index, sha in enumerate(shas)
    ]
    batch_size: Final = 40
    for offset in range(0, len(aliases), batch_size):
        batch = aliases[offset : offset + batch_size]
        query = (
            f"query {{ repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) "
            f"{{ {' '.join(expression for _, _, expression in batch)} }} }}"
        )
        result = run_text([gh, "api", "graphql", "-F", "query=@-"], stdin=query)
        if result.returncode:
            msg = result.stderr.strip() or "could not read GitHub pull requests"
            raise ValueError(msg)
        try:
            response = json.loads(result.stdout)["data"]["repository"]
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            msg = "invalid GitHub associated pull requests response"
            raise ValueError(msg) from error
        for alias, identifier, _ in batch:
            pulls[identifier] = _read_alias(response, alias, identifier)
    return pulls


def _read_alias(response: object, alias: str, identifier: str) -> PullRequest:
    if not isinstance(response, dict):
        msg = f"invalid pull request response for {identifier}"
        raise TypeError(msg)
    if (pull := response.get(alias)) is None:
        msg = f"missing pull request response for {identifier}"
        raise ValueError(msg)
    if not isinstance(pull, dict):
        msg = f"invalid pull request response for {identifier}"
        raise TypeError(msg)
    associated = pull.get("associatedPullRequests")
    if not isinstance(associated, dict) or not isinstance(nodes := associated.get("nodes"), list):
        msg = f"invalid pull request response for commit {identifier}"
        raise TypeError(msg)
    merged = [item for item in nodes if _is_squash_pull(item, identifier)]
    if len(merged) != 1:
        msg = f"expected one squash-merged pull request for commit {identifier}, found {len(merged)}"
        raise ValueError(msg)
    return _pull_request(merged[0], f"commit {identifier}")


def _is_squash_pull(pull: object, sha: str) -> bool:
    if not isinstance(pull, dict) or pull.get("mergedAt") is None:
        return False
    return bool(isinstance(commit := pull.get("mergeCommit"), dict) and commit.get("oid") == sha)


def _pull_request(response: dict[str, object], source: str) -> PullRequest:
    number, author = response.get("number"), response.get("author")
    if not isinstance(number, int) or isinstance(number, bool) or not isinstance(author, dict | None):
        msg = f"invalid pull request response for {source}"
        raise TypeError(msg)
    if number < 1:
        msg = f"invalid pull request number for {source}: {number}"
        raise ValueError(msg)
    account = github_account(author, number)
    return PullRequest(number=str(number), credits=_credits(account, response.get("mergeCommit"), number))


def github_account(account: dict[str, object] | None, number: int) -> PullRequestAuthor:
    """Classify a GitHub actor the way pull request credits do.

    :param account: GraphQL actor with ``login`` and ``__typename``; ``None`` for a deleted account.
    :param number: Pull request number used in errors.
    :returns: The handle, with any ``[bot]`` suffix removed, and whether it is a bot.
    :raises ValueError: The actor has no login or an unsupported account type.
    """
    login, account_type = (
        ("ghost", "User")
        if account is None or account.get("__typename") == "Mannequin"
        else (account.get("login"), account.get("__typename"))
    )
    if not isinstance(login, str) or account_type not in {"User", "Bot"}:
        msg = f"invalid GitHub author for pull request #{number}"
        raise ValueError(msg)
    bot = account_type == "Bot" or login.endswith("[bot]")
    return PullRequestAuthor(handle=login.removesuffix("[bot]") if bot else login, is_bot=bot)


def _credits(author: PullRequestAuthor, commit: object, number: int) -> tuple[PullRequestCredit, ...]:
    authors = commit.get("authors") if isinstance(commit, dict) else None
    if not isinstance(authors, dict) or not isinstance(nodes := authors.get("nodes"), list):
        msg = f"invalid merge commit authors for pull request #{number}"
        raise TypeError(msg)
    entries: dict[tuple[bool, str], tuple[PullRequestCredit, bool]] = {}
    if author.handle.casefold() not in AI_ASSISTANT_LOGINS:
        entries[True, author.handle.casefold()] = (PullRequestCredit(name=author.handle, linked=True), author.is_bot)
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(user := node.get("user"), dict | None):
            msg = f"invalid merge commit author for pull request #{number}"
            raise TypeError(msg)
        if isinstance(email := node.get("email"), str) and _RE_AI_ASSISTANT_EMAIL.search(email):
            continue
        if user is None:
            if isinstance(name := node.get("name"), str) and name.strip():
                entries.setdefault((False, name.casefold()), (PullRequestCredit(name=name, linked=False), False))
            continue
        if (account := github_account(user, number)).handle.casefold() in AI_ASSISTANT_LOGINS:
            continue
        entries.setdefault(
            (True, account.handle.casefold()), (PullRequestCredit(name=account.handle, linked=True), account.is_bot)
        )
    humans = tuple(credit for credit, bot in entries.values() if not bot)
    return humans or tuple(credit for credit, _ in entries.values())


@dataclass(frozen=True, kw_only=True)
class PullRequestAuthor:
    """GitHub account attached to a merged pull request."""

    handle: str
    is_bot: bool


@dataclass(frozen=True, kw_only=True)
class PullRequestCredit:
    """Account or commit trailer name the linker credits for a merged pull request."""

    name: str
    linked: bool


@dataclass(frozen=True, kw_only=True)
class PullRequest:
    """Merged pull request associated with a fragment."""

    number: str
    credits: tuple[PullRequestCredit, ...]


__all__ = [
    "AI_ASSISTANT_LOGINS",
    "PullRequest",
    "PullRequestAuthor",
    "PullRequestCredit",
    "fragment_pull_requests",
    "github_account",
]
