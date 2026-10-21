#####################################
 Resume a partial PyPI upload safely
#####################################

PyPI uploads one distribution file at a time. A failed job can leave a release with some wheels but no sdist, or the
reverse. Before retrying, compare the complete local ``dist`` directory with the files already on PyPI. The
``artifacts`` command uses PyPI's `release JSON API <https://docs.pypi.org/api/json/#get-a-release>`_ and checks each
filename and SHA256 digest.

Stage the files PyPI lacks in a fresh directory:

.. code-block:: bash

    release-creator artifacts \
      --project example --version 1.2.3 --dist dist \
      --mode stage --missing-dir "$RUNNER_TEMP/missing" \
      --github-output "$GITHUB_OUTPUT"

The command prints the missing file count and writes ``missing_count=N`` to the GitHub step output. Pass the staged
directory to the trusted publisher only when the count is greater than zero. Keep the full ``dist`` directory for the
post-upload check:

.. code-block:: bash

    release-creator artifacts \
      --project example --version 1.2.3 --dist dist --mode verify \
      --wait-seconds 120

``verify`` succeeds only when PyPI has every local file with the same digest and has no extra file for that version. A
404 before upload means none of the files has been published. Other HTTP errors, invalid responses, yanked files, an
empty local directory, and any unexpected or changed file fail the job. The command never uploads files or uses a
publishing credential. The bounded wait covers PyPI JSON propagation after an upload; it retries only an incomplete
release and fails at the deadline. Keep the upload and its OIDC environment in the caller workflow.
