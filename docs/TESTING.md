# Testing Guide

## 1. Automated tests (backend)
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest -v
```
These 25 tests run without internet access and without an AWS account:

| File | What it proves |
|---|---|
| `test_sequence.py` | FASTA parsing, lowercase/whitespace/numbers handling, invalid letters, DNA detection, length limits, 31-feature vector, ubiquitin MW ≈ 8.6 kDa |
| `test_workflow.py` | B starts only after A, each of C–H starts only after B, and I starts only after all of C–H. Parallel is faster than sequential. One failed task does not stop the report. A failure in A skips everything downstream. Benchmark speed-up |
| `test_api.py` | Health endpoint, 422 for invalid input, full job in local mode, H *skipped* when no engine is set, downloads, history, delete, sequential mode, CORS allows only configured origins |
| `test_s3_and_engine.py` | Uses **moto**, an in-memory S3 emulator. Uploads to S3 under `jobs/<id>/`, presigned URLs (signature + 900 s expiry), reading the PDB back, deleting S3 objects, missing bucket → local fallback + warning, ESMFold connection error → H *failed* but report still produced, wrong-length structure rejected, readable AWS error messages |

The ESMFold HTTP call is replaced by a test stub in these tests. Live ESMFold is checked manually (section 3).

## 2. Manual test plan (frontend + backend)
| # | Input / action | Expected result |
|---|---|---|
| 1 | Click *Human ubiquitin*, then Submit (parallel, 1 s delay) | Redirects to Workflow. C–G run together (timeline bars overlap). Status *completed*. Total ≈ 1 s + ESMFold time |
| 2 | Same, but **sequential** mode | Timeline bars run one after another. C–G stage ≈ 5 s |
| 3 | Performance → Run benchmark (1 s) | Sequential ≈ 5 s, parallel ≈ 1 s, speed-up ≈ 5× |
| 4 | Performance → Run benchmark (0 s) | Both take a few ms. Speed-up ≈ 1× or below (explained on the page) |
| 5 | Plain text without a header: `mqifvktltgktitlevepsdtienvkakiqdkeg` | Accepted (uppercased). Name "Unnamed sequence" |
| 6 | Sequence with spaces, line breaks, numbers and a trailing `*` | Accepted. These characters are removed |
| 7 | `HELLO WORLD 123 BJ` | Error: *Invalid character(s) B, J, O at position(s) …* |
| 8 | `ATGGCGTACGTTAGCATCGA` (DNA) | Error: *This looks like a DNA/RNA sequence…* |
| 9 | `MQIFV` (5 aa) | Error: *too short … Minimum is 10* |
| 10 | 401+ residues | Error: *too long … Maximum is 400* |
| 11 | Empty box → Submit | *Please paste a protein sequence…* |
| 12 | FASTA with two records | Only the first record is analysed |
| 13 | Results → Download each file | Files download. On AWS the link host is `YOUR-BUCKET.s3.<region>.amazonaws.com` |
| 14 | Wait more than 15 min, reuse an old link | S3 returns *Request has expired*. *Refresh links* fixes it |
| 15 | History → Delete | Row disappears. S3 objects are removed |
| 16 | Stop the backend, reload the Dashboard | Red message: *Cannot reach the backend at …* |
| 17 | Set `PREDICTION_ENGINE=none`, restart, submit | Yellow banner. H *skipped*. Results say *3D structure prediction is not available*. No structure files are stored |
| 18 | Set a wrong `S3_BUCKET_NAME`, restart, submit | Health *degraded*. Job completes. Files stored on server disk. Warning names the bucket problem |
| 19 | Detach the IAM role (EC2 → Modify IAM role → No role), wait ~1 min, check Cloud Status | *No AWS credentials found…* or *Access denied…*. Re-attach the role to fix it |

## 3. Verifying the real ESMFold integration
On the deployed server (or your PC with internet access):
```bash
curl -s -X POST --data "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG" \
  https://api.esmatlas.com/foldSequence/v1/pdb/ | head -3
```
You should see `ATOM` lines (PowerShell: use `curl.exe` instead of `curl`). For ubiquitin, the predicted
model should show the well-known β-grasp fold, with a high mean pLDDT. If the command fails, see
*ESMFold* in TROUBLESHOOTING.md.

## 4. AWS verification checklist
See *Step 10* of AWS_DEPLOYMENT.md. Capture screenshots of each tick for your report.
