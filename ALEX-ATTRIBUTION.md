# Alex CLI/usability workstream provenance

Alex Kendall's validated external patch could not be transferred through the peer channel.

- Author account claim: `dumbie5547` (public account exists; write permission is not verified and no authenticated GitHub connection is available)
- Base: `e2b37753466bd702a9735fe4234d7fbb4a07ec54`
- External patch name: `alex-cli-usability-4396e06f.patch`
- External SHA-256: `b0081e613fce417ae78add90ab6ca7911b8ae543cf776b3e9c4b7c606e83b227`
- Reported scope: README, argparse, board display, undo/correction, EOF handling
- Reported size/tests: 4 files, +329/-43, five CLI tests, fresh-clone checks passed

The local `tritowers_cli.py` and `test_cli.py` are an independent reimplementation from that scope/interface report, not a byte-for-byte copy. Preserve this note when reconciling with Alex's original patch later.
