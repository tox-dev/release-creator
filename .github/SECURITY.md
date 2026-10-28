# Security policy

release-creator is a command-line tool that validates news fragments, links them to pull requests and authors, renders
changelog sections into GitHub Release notes, and checks published JetBrains plugin archives. This policy says how to
report a security problem and how we decide whether a report is one.

## Reporting a vulnerability

**Do not open a public issue for a security problem.** Use
[GitHub's private vulnerability reporting](https://github.com/tox-dev/release-creator/security/advisories/new). If
neither works for you, email [gaborjbernat@gmail.com](mailto:gaborjbernat@gmail.com).

Include what the attacker controls and what they gain, the steps or a proof of concept, and the versions and platform
you tested. Write the report yourself; unreviewed tool or model output takes longer to triage.

## What to expect

Volunteers maintain release-creator, with no on-call rotation. We aim to acknowledge a report within **5 working days**
and assess it within **15 working days**. Fixes are developed in a private fork attached to the draft advisory, ship in
a new release, and the advisory, with a CVE requested through GitHub, goes out with that release. The default embargo is
**90 days** from the report; we agree any change with the reporter. We credit reporters in the advisory under the name
they choose, or not at all. There is no bug bounty.

## Supported versions

Only the latest release receives fixes. Confirm the problem reproduces on it before reporting.

## Vulnerability or bug

A report is a vulnerability when an attacker who controls only an input that the [threat model](THREAT_MODEL.md) lists
as untrusted breaks a guarantee release-creator makes. A report that first needs control of something the threat model
trusts, such as the repository's Git history, the GitHub API answers `gh` returns, or the caller's options, is a bug: we
fix it in the open and publish no advisory. Classify by who supplies the dangerous input, not by how bad the outcome
sounds.

**In scope**

- A fragment from a pull request passing `validate-news` while it carries a hand-written author credit or pull request
  link, so release notes credit or link someone the history does not show.
- Fragment or changelog text breaking out of its section in rendered notes, for example to add a fake `New Contributors`
  or `Full Changelog` entry.
- A plugin ZIP comparison reporting a match when member contents, types or permissions differ.
- Data from Git or GitHub reaching a GraphQL query or a command as anything but data.

**Out of scope**

- The wording of a fragment: maintainers review it before it merges, as they review code.
- The token `gh` uses and what that token may do.
- Mentions in rendered notes that GitHub turns into notifications.
- Correctness of `towncrier` itself.

If you cannot tell which side a finding falls on, report it privately and we will decide.
