# CSI-PAIRS anonymous supplementary

This package contains the formal implementation, tests, frozen configurations, data contract,
paper source, and official conference style files. It contains no formal dataset, experiment result,
checkpoint, internal repository provenance, or author identity.

Third-party inputs are not bundled. Their immutable versions, source URLs, licenses, and SHA-256
digests are recorded in `formal_v2/configs/waibu_resources_v1.json`. Resources whose recorded
license does not grant downstream redistribution must be obtained by each user from the source URL.
Local byte authentication does not establish paper fidelity or scientific evidence.

Run the code tests with Python 3.12 after installing `formal_v2/requirements-lock.txt`:

```bash
python3 -m unittest discover -s formal_v2/tests -v
```

Fixtures are permanently marked `scientific_use=FORBIDDEN`. Formal claims remain blocked until the
non-fixture data, independent regeneration, calibration, external-validity, and statistical gates
complete under the frozen protocol.
