###############################
 Where release data comes from
###############################

Each part of a release has one source. Towncrier builds the changelog from reviewed fragments. ``tags`` checks the
version against existing tags. ``notes`` prints the tagged changelog section, and GitHub's generated notes add the pull
request list, the author credits, the new contributors, and the comparison link.

.. mermaid::
    :alt: The tagged changelog section and GitHub generated notes together form the GitHub Release body.
    :caption: Sources for a GitHub Release body
    :align: center

    flowchart LR
       changelog["Tagged changelog"] --> notes["release-creator notes"]
       notes --> release["GitHub Release body"]
       generated["GitHub generated notes"] --> release
       classDef source fill:#dbeafe,stroke:#2563eb,color:#0f172a;
       classDef step fill:#ede9fe,stroke:#7c3aed,color:#0f172a;
       classDef result fill:#dcfce7,stroke:#16a34a,color:#0f172a;
       class changelog,generated source;
       class notes step;
       class release result;

Why fragments come before the changelog
=======================================

Someone writing a change does not know the pull request number yet. A ``+name`` fragment lets them describe the
user-visible result when they write the code. One pull request may carry several fragments, so each distinct change
keeps its own entry. Towncrier later collects those entries and removes their fragment files.

The project owner decides whether a change is user-visible and which category fits it; neither Towncrier nor
release-creator can infer that from a commit title. Maintenance work stays out of the changelog unless the pull request
contains a user-visible change.

Why credits come from GitHub
============================

GitHub knows who authored each merged pull request, so ``gh release create --generate-notes`` credits them without a
lookup that depends on squash merges. Bots can be left out through ``changelog.exclude.authors`` in
``.github/release.yml``. The docs changelog keeps the curated text: a numbered fragment still gets its ``issue_format``
link, but a ``+name`` fragment gets no pull request link and no ``by @handle`` credit unless its author writes one.

Why notes read a tag
====================

The tag identifies the source that produced the published artifact. Reading that checkout's changelog keeps the GitHub
description tied to reviewed release entries, in their order and categories. ``notes`` copies the section as written, so
the release body is the reviewed text and not a rendering of it.
