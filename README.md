# Reference code

`packed_parser.py` is tested seed code: packed-file repair, report fingerprinting, college resolution, normalization helpers. The AI agents port it into `backend/app/pipeline` (prompt P03) and extend it.

- `test_packed_parser.py`: synthetic tests (`python -m pytest reference -q`).
- `verify_on_real_files.py`: prints the figures in `docs/04` section 12. Run it only on a secured host with the real files; never inside an AI tool.
- `VERIFIED_RESULTS.txt`: output from 8 Oct 2026 on the four AIBT files.
