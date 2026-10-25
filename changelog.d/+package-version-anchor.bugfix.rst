``notes --package`` and ``contributors --package`` keep a package version anchor that sits directly after its own
version heading inside that version's section. Before, the anchor ended the section, so ``notes`` rendered toml-fmt
releases with only the Full Changelog link. ``notes`` leaves the version anchor out of the release body, which starts
at the first category anchor.
