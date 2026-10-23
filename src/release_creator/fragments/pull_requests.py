"""Read the pull requests associated with fragment commits."""

# ruff: file-ignore[lazy-import-immediately-resolved]  # The shared regex and dataclass decorators resolve during module load.
from __future__ import annotations

lazy import json
lazy import shutil
lazy from dataclasses import dataclass
lazy from typing import Final, cast

lazy from release_creator.process import run_text


def fragment_pull_requests(repository: str, commits: dict[str, str]) -> dict[str, PullRequest]:
    """Resolve each fragment through GitHub's commit-to-pull-request API.

    :param repository: GitHub owner and repository.
    :param commits: Fragment names mapped to introducing commit hashes.
    :returns: Fragment names mapped to the merged pull request and its author.
    """
    gh = cast("str", shutil.which("gh"))
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
                "{ nodes { number mergedAt author { login __typename } mergeCommit { oid } } } } }"
            ),
        )
        for index, sha in enumerate(shas)
    ]
    batch_size: Final = 100
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
    login, account_type = ("ghost", "User") if author is None else (author.get("login"), author.get("__typename"))
    if not isinstance(login, str) or account_type not in {"User", "Bot"}:
        msg = f"invalid GitHub author for pull request #{number}"
        raise ValueError(msg)
    bot = account_type == "Bot"
    handle = login.removesuffix("[bot]") if bot else login
    return PullRequest(number=str(number), author=PullRequestAuthor(handle=handle, is_bot=bot))


@dataclass(frozen=True, kw_only=True)
class PullRequestAuthor:
    """GitHub account attached to a merged pull request."""

    handle: str
    is_bot: bool


@dataclass(frozen=True, kw_only=True)
class PullRequest:
    """Merged pull request associated with a fragment."""

    number: str
    author: PullRequestAuthor


__all__ = [
    "PullRequest",
    "PullRequestAuthor",
    "fragment_pull_requests",
]
