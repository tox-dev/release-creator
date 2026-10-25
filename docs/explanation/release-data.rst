###############################
 Where release data comes from
###############################

Each release command uses a different source. ``fragments`` gets pull request numbers from squash commits. Towncrier
builds the changelog from reviewed fragments. ``tags`` checks the version against existing tags. ``notes`` reads the
tagged changelog to make the GitHub description.

.. mermaid::
    :alt: The tagged changelog provides changes and authors.
    :caption: Sources for a GitHub Release body
    :align: center

    flowchart LR
       changelog["Tagged changelog"] --> render["release-creator notes"]
       render --> release["GitHub Release body"]
       classDef source fill:#dbeafe,stroke:#2563eb,color:#0f172a;
       classDef step fill:#ede9fe,stroke:#7c3aed,color:#0f172a;
       classDef result fill:#dcfce7,stroke:#16a34a,color:#0f172a;
       class changelog source;
       class render step;
       class release result;

Why fragments come before the changelog
=======================================

Someone writing a change does not know the pull request number yet. A named fragment lets them describe the user-visible
result when they write the code. After squash merge, ``fragments`` reads the commit subject and adds the PR link and the
credit computed from its merge commit's authors. One pull request may carry several fragments, so each distinct change
keeps its own entry. Towncrier later collects those entries and removes their fragment files.

Towncrier's template sets the changelog layout and stable anchors. Each project configures its own fragment categories.
The project owner decides whether a change is user-visible and which category fits it; neither Towncrier nor
release-creator can infer that from a commit title. Maintenance work stays out of the changelog unless the pull request
contains a user-visible change.

Why notes read a tag
====================

The tag identifies the source that produced the published artifact. Reading that checkout's changelog keeps the GitHub
description tied to reviewed release entries. The changelog supplies their order, categories, and author credits.
``notes`` changes the presentation for GitHub, including unwrapped bullets, category names, mentions, and comparison
links. It does not build a change list from commit subjects.

``notes`` does not read GitHub's generated notes, and it does not check changelog credits: the fragment linker credits
the merged PR's author and its merge commit's authors and co-authors, without AI assistants, and ``validate-news``
rejects fragments that credit someone by hand. A bot pull request has no news entry unless it supplies a fragment for a
user-visible change, and a bot is credited only when it is the only author.
