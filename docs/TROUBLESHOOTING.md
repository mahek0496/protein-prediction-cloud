# Troubleshooting

## Windows / local setup
| Symptom | Fix |
|---|---|
| `py` or `python` not recognised | Reinstall Python 3.12 and tick **Add python.exe to PATH**. Close and reopen VS Code |
| `Activate.ps1 cannot be loaded because running scripts is disabled` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, answer **Y**, then activate again |
| `pip install` fails building numpy/biopython | You are on a Python version without prebuilt wheels. Use Python 3.11 or 3.12 (`py -3.12 -m venv .venv`) |
| `uvicorn` not recognised | The venv isn't active. Run `.\.venv\Scripts\Activate.ps1`, or use `python -m uvicorn app.main:app --reload` |
| `ModuleNotFoundError: No module named 'app'` | Run uvicorn from inside the `backend` folder |
| Port 8000 / 5173 already in use | Close the other terminal, or use `--port 8001` and update `VITE_API_BASE_URL` |
| `npm` not recognised | Install Node.js LTS, then reopen VS Code |
| VS Code uses the wrong Python | Ctrl+Shift+P → *Python: Select Interpreter* → `backend\.venv\Scripts\python.exe` |
| Changed `frontend\.env` but nothing happened | Vite reads `.env` only at start-up. Stop `npm run dev` (Ctrl+C) and start it again |

## Frontend ↔ backend connection
| Symptom | Cause / fix |
|---|---|
| Red box: *Cannot reach the backend at http://…* | Backend not running, wrong `VITE_API_BASE_URL`, EC2 security group missing port 8000 for your IP, or a CORS rejection |
| Browser console: *blocked by CORS policy* | Add the **exact** frontend origin (scheme + host + port, no trailing slash) to `CORS_ORIGINS` in `backend/.env`, then restart the backend. Example: `http://localhost:5173` |
| Works from EC2 (`curl localhost:8000`) but not from your PC | Security-group inbound rule missing, or your IP changed (*My IP* rules go stale). Edit the rule |
| Site on `https://…` cannot call an `http://` backend | Browsers block mixed content. Use Option B (nginx, same origin) or put HTTPS on the backend |
| Page refresh on `/results/...` gives 404 under nginx | The `try_files … /index.html` line is missing from the nginx config |

## AWS S3 / IAM (the messages come from the app's own error handling)
| Message on the Cloud Status page / in job warnings | Fix |
|---|---|
| *No AWS credentials found* | On EC2: attach `ProteinAppEC2Role` (Actions → Security → Modify IAM role). On your PC: `aws configure`, or set `STORAGE_BACKEND=local` |
| *Access denied by AWS (AccessDenied)* | The policy's bucket name or prefix doesn't match. The resource must be `arn:aws:s3:::<bucket>/jobs/*` and `S3_PREFIX=jobs`. Check the policy is attached to the role |
| *S3 bucket '…' was not found* | Typo in `S3_BUCKET_NAME`, or the bucket was deleted |
| *Bucket … is in a different region* | Set `AWS_REGION` to the bucket's region (shown in the S3 console) |
| *Amazon S3 is unreachable* | Instance has no outbound internet (check the security group's outbound rules and the subnet's route to an internet gateway), or AWS is having an outage |
| Credential source shows `env` or `shared-credentials-file` on EC2 | Access keys are set somewhere (`backend/.env`, `~/.aws/credentials` or environment variables). Remove them so the IAM role is used |
| Presigned link: *Request has expired* | Expected after 15 minutes. Click **Refresh links** |
| Presigned link: *SignatureDoesNotMatch* / redirect error | `AWS_REGION` differs from the bucket's region |
| Presigned link: *AccessDenied* right away | The role lacks `s3:GetObject` on `jobs/*` (needed to sign download links) |
| `aws sts get-caller-identity` fails on EC2 | Role not attached, or the instance metadata service is disabled. Check *Instance metadata options*: it should be *Enabled* |
| Jobs complete but files say "Server disk" | S3 upload failed. The warning text says why (see the rows above). Results are still saved locally |

## ESMFold (Task H)
| Symptom | Fix |
|---|---|
| H failed: *Could not connect to ESMFold via Meta ESM Atlas API* | No outbound internet, or the public ESM Atlas service is down (it has had outages). Test with the curl command in TESTING.md. Alternatives: `PREDICTION_ENGINE=nvidia` with `NVIDIA_API_KEY`, or `PREDICTION_ENGINE=none` |
| H failed: *returned HTTP 4xx/5xx* | Sequence too long for the service (keep it ≤ 400 aa), rate limiting, or a service outage. Retry later |
| H failed: *timed out* | Long sequence or busy server. Increase `PREDICTION_TIMEOUT_SECONDS` |
| SSL certificate error to api.esmatlas.com | A known intermittent server-side certificate-chain issue. Try again later, or use the NVIDIA engine |
| H skipped | `PREDICTION_ENGINE=none`. This is intentional: no 3D structure is shown or stored |
| 3D viewer is empty | Check the browser console. The structure is read from S3 through `/api/results/<id>/structure`, so S3 read errors appear there |

## EC2 service
```bash
sudo systemctl status protein-api        # is it running?
journalctl -u protein-api -n 100         # last 100 log lines (startup shows storage + engine status)
sudo systemctl restart protein-api       # after editing backend/.env
curl -s localhost:8000/api/health        # health from the instance itself
```
| Symptom | Fix |
|---|---|
| `status=203/EXEC` | `.venv` path wrong. Run `deploy/setup_ec2.sh` from the project folder, and check the paths in the service file |
| `dnf: No match for argument: python3.11` | Use `sudo dnf install -y python3.12 python3.12-pip` and replace `python3.11` with `python3.12` in `setup_ec2.sh` |
| SSH: *UNPROTECTED PRIVATE KEY FILE* on Windows | Run the two `icacls` commands in AWS_DEPLOYMENT.md, Step 5 |
| SSH: *Connection timed out* | Security group SSH rule not set to your current IP, or the instance is stopped |
| Jobs stuck as "failed: Server restarted…" | The service restarted mid-job. Resubmit |
