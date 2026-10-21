###########################################
 Check a plugin before a Marketplace retry
###########################################

A JetBrains Marketplace upload can succeed before a later GitHub Release step fails. On a retry, check the existing
plugin version against the signed ZIP from the tagged build before calling ``publishPlugin`` again. Marketplace can
repackage the outer ZIP, so compare each member path and its uncompressed SHA256 digest instead of the outer file hash.

Run the check after building and validating the signed ZIP, in a step without the Marketplace upload token:

.. code-block:: bash

    release-creator marketplace \
      --plugin-id com.example.plugin \
      --version 2.4.6 \
      --archive build/distributions/example-2.4.6-signed.zip \
      --github-output "$GITHUB_OUTPUT"

The step prints and writes ``publish=true`` when the version-specific download returns 404. Publish only in that case.
If the download exists, ``publish=false`` means every ZIP member matched. A changed, extra, missing, or duplicate member
fails the check. Non-404 HTTP failures and invalid ZIPs also fail. The command uses JetBrains' `version-specific
download endpoint <https://plugins.jetbrains.com/docs/marketplace/plugin-update-download.html>`_ and never uploads or
reads a publishing credential.

In GitHub Actions, give the check step an ID and gate the upload step on its output:

.. code-block:: yaml

    - name: Check the published plugin
      id: marketplace
      run: |
        release-creator marketplace \
          --plugin-id com.example.plugin \
          --version 2.4.6 \
          --archive build/distributions/example-2.4.6-signed.zip \
          --github-output "$GITHUB_OUTPUT"
    - name: Publish the signed plugin
      if: steps.marketplace.outputs.publish == 'true'
      env:
        PUBLISH_TOKEN: ${{ secrets.PUBLISH_TOKEN }}
      run: ./gradlew publishPlugin

An uploaded version might not be publicly downloadable until JetBrains approves it. During that interval, 404 cannot
prove whether the upload has already happened; a repeat upload may fail. Keep that failure visible and retry after the
version appears publicly. To check an already visible version after publication, pass ``--mode verify``; a 404 then
fails instead of returning ``publish=true``.
