####################################
 Verify a complete PyPI publication
####################################

PyPI uploads distribution files one at a time. A failed publishing job can leave a partial release. The publisher should
retry the complete validated ``dist`` directory without ``skip-existing``. PyPI accepts byte-identical reuploads and
rejects files whose bytes changed.

After publishing, verify the full local distribution against PyPI's `Simple JSON API
<https://packaging.python.org/en/latest/specifications/simple-repository-api/>`_:

.. code-block:: bash

    release-creator artifacts \
      --project example --version 1.2.3 --dist dist \
      --wait-seconds 120 > published-urls.txt

The command checks every filename and SHA256 digest, rejects unexpected files and yanked files, and prints one published
URL per file. It waits only for an incomplete PyPI listing; changed bytes and malformed responses fail immediately. The
command neither uploads files nor uses publishing credentials.

Verify provenance for each published URL in a separate job with ``pypi-attestations verify pypi --repository``. The
shared ``reconcile-pypi-artifacts`` Action performs both checks.
