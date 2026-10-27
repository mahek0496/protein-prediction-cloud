# Cloud Application for Biology: Protein Structure Prediction

A web application that takes a protein amino-acid sequence, runs a dependency-aware analysis workflow
with parallel tasks, predicts a 3D structure with **ESMFold** (when a prediction service is reachable),
and stores the reports and structure files in **Amazon S3**. The FastAPI backend runs on **Amazon EC2**
and reaches S3 through an **IAM role**, so no AWS keys exist in the code, config files or browser.

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite, React Router, Recharts, 3Dmol.js |
| Backend | Python 3.11/3.12, FastAPI, Biopython, `concurrent.futures`, SQLite |
| Cloud | Amazon EC2 (compute), Amazon S3 (result storage), AWS IAM (role-based access), boto3 |
| 3D prediction | ESMFold (Lin et al., *Science* 2023) through the Meta ESM Atlas API or NVIDIA's hosted API |

> **Read first: what is real and what is not**
> - **Task H is a genuine prediction.** The app sends the sequence to an ESMFold server and stores the PDB it returns, along with an mmCIF conversion and per-residue pLDDT confidence. If no engine is configured or reachable, Task H is marked *skipped* or *failed*. The app never invents coordinates.
> - **Tasks D and F** are deterministic calculations, such as molecular weight and pI. **Task C** is an empirical Chou-Fasman-style propensity *estimate* (roughly 50–60% accurate), not a structure prediction. **Tasks E and G** are rule-based screens that flag *candidate* sites. Every result carries one of these labels in the UI and in the reports.
> - The optional **artificial demo delay** is a `sleep()` added to Tasks C–G so the parallel speed-up is visible on screen. Whenever it is on, the workflow page and every report say so.

---

## 1. Abstract
Determining a protein's 3D structure experimentally is slow and expensive. Deep-learning predictors such as
ESMFold can produce structures from sequence alone, but they need GPU servers. This project builds a cloud
application. A lightweight web front end lets users submit sequences. A central backend on Amazon EC2
orchestrates a parallel analysis workflow and calls a remote ESMFold service. Durable results are stored in
Amazon S3 and shared through time-limited presigned URLs. Access control uses an AWS IAM role with
least-privilege permissions.

## 2. Problem statement
Biology students and researchers need a simple way to analyse a protein sequence and obtain a predicted
structure, without installing bioinformatics software or managing GPUs. They also need to keep and share
the results. A desktop script cannot do this. It does not scale, it keeps results on one machine, and it
runs every analysis one after another.

## 3. Objectives
1. Accept FASTA or plain-text sequences in the browser, with clear validation messages.
2. Run a task graph (A → B → C–H in parallel → I) with enforced dependencies and timing for every task.
3. Integrate a genuine structure predictor (ESMFold) and label every non-prediction result honestly.
4. Store reports and PDB/mmCIF files in Amazon S3, and download them through presigned URLs.
5. Deploy the backend on EC2 using an IAM role (no hardcoded keys).
6. Demonstrate sequential versus parallel execution with measured times.

## 4. Existing system vs proposed system
| Existing (typical) | Proposed |
|---|---|
| Standalone scripts on one PC | Web app: any browser, central server on EC2 |
| Analyses run one after another | Independent analyses run concurrently (ThreadPoolExecutor) |
| Results kept on a local disk | Results stored durably in Amazon S3, with history in SQLite |
| Credentials often pasted into code | IAM role on EC2 supplies temporary credentials automatically |
| Simulated "predictions" sometimes shown as real | Real ESMFold output, with every other result clearly labelled |

## 5. System architecture
```
 ┌───────────────────────┐   HTTPS/HTTP (JSON)    ┌──────────────────────────────────────────────┐
 │ Browser (React + Vite) │ ─────────────────────▶ │ Amazon EC2  (Amazon Linux 2023)              │
 │  • sequence form       │ ◀───────────────────── │  FastAPI + Uvicorn (systemd service)         │
 │  • workflow graph      │   job status / results │   ├─ Workflow engine (ThreadPoolExecutor)    │
 │  • 3Dmol.js viewer     │                        │   ├─ SQLite (history)                        │
 │  • charts (Recharts)   │                        │   └─ boto3 ──┐  credentials from IAM role    │
 └─────────┬─────────────┘                         └──────────────┼───────────────┬───────────────┘
           │ presigned GET URL (expires in 15 min)                │ PutObject     │ HTTPS POST sequence
           ▼                                                      ▼               ▼
 ┌──────────────────────────┐                     ┌────────────────────────┐  ┌───────────────────────┐
 │ Amazon S3 bucket         │ ◀───────────────────│ IAM role               │  │ ESMFold prediction API │
 │  jobs/<id>/report.json   │                     │ ProteinAppEC2Role      │  │ (ESM Atlas or NVIDIA)  │
 │  jobs/<id>/report.md     │                     │ least-privilege policy │  └───────────────────────┘
 │  jobs/<id>/structure.pdb │                     └────────────────────────┘
 │  jobs/<id>/structure.cif │
 └──────────────────────────┘
```

## 6. Task dependency graph
```
            A  Sequence validation & analysis
            │
            B  Numerical feature vector (31 features)
            │
 ┌──────┬───┴──┬──────┬──────┬──────┐   ← started together once B finishes
 C      D      E      F      G      H
 SS     Phys-  Hydro- Charge Motif  ESMFold 3D
 prop.  chem   pathy  vs pH  scan   prediction
 └──────┴───┬──┴──────┴──────┴──────┘
            I  Final report (waits for all of C–H; tolerates individual failures)
            │
          UPLOAD  report.json, report.md, structure.pdb, structure.cif → Amazon S3
```
The scheduler (`backend/app/workflow/dag.py`) submits a task only after every task it depends on has
finished. If A fails, everything downstream is *skipped*. If one of C–H fails, I still builds the report
and records the error.

## 7. Modules
| Module | File | Purpose |
|---|---|---|
| Task A | `services/sequence.py` | FASTA parsing, alphabet/length validation, DNA detection, composition |
| Task B | `services/features.py` | 20 composition fractions + 11 physicochemical values |
| Task C | `services/analysis.py` | Chou-Fasman propensity scan (empirical estimate) |
| Task D | `services/analysis.py` | ProtParam: MW, pI, GRAVY, instability, extinction coefficient |
| Task E | `services/analysis.py` | Kyte-Doolittle hydropathy + transmembrane candidate screen |
| Task F | `services/analysis.py` | Net charge vs pH curve, pI category |
| Task G | `services/analysis.py` | N-glycosylation motif (PROSITE PS00001), cysteines, low complexity |
| Task H | `services/structure_engine.py` | ESMFold call, pLDDT parsing, PDB → mmCIF conversion |
| Task I | `workflow/pipeline.py` + `services/report.py` | Combines results, writes JSON + Markdown report |
| Storage | `services/storage.py` | S3 (boto3, presigned URLs, error translation) or local-disk fallback |
| Scheduler | `workflow/dag.py` | Dependency-aware parallel/sequential executor with timings |
| API | `routes/*.py` | REST endpoints, validation, CORS |
| Database | `database.py` | SQLite job history |

## 8. Project structure
```
protein-prediction-cloud/
├── backend/
│   ├── app/
│   │   ├── main.py               FastAPI app, CORS, startup
│   │   ├── config.py             environment variables
│   │   ├── database.py           SQLite
│   │   ├── models/schemas.py     request models
│   │   ├── routes/               jobs.py, history.py, system.py
│   │   ├── services/             sequence, features, analysis, structure_engine, storage, report
│   │   └── workflow/             dag.py (scheduler), pipeline.py (tasks A–I)
│   ├── tests/                    pytest suite (S3 tested with moto emulator)
│   ├── requirements.txt / requirements-dev.txt
│   └── .env.example
├── frontend/
│   ├── src/  App.jsx, main.jsx, index.css, pages/, components/, services/
│   ├── package.json, vite.config.js, .env.example
├── deploy/   iam-policy.json, ec2-trust-policy.json, protein-api.service, nginx-protein.conf, setup_ec2.sh
└── docs/     AWS_DEPLOYMENT.md, TESTING.md, TROUBLESHOOTING.md, VIVA_GUIDE.md
```

## 9. Run locally on Windows (VS Code)
**Install once:** [Python 3.12](https://www.python.org/downloads/) (tick *Add python.exe to PATH*),
[Node.js LTS](https://nodejs.org/), and [VS Code](https://code.visualstudio.com/) with the Python extension.
Unzip the project, then open the folder in VS Code (*File → Open Folder*). Open a terminal with
*Terminal → New Terminal* (PowerShell).

### 9.1 Backend (terminal 1)
```powershell
cd backend
py -3.12 -m venv .venv                 # or: python -m venv .venv
.\.venv\Scripts\Activate.ps1           # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements-dev.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```
Open http://localhost:8000/docs (interactive API docs) and http://localhost:8000/api/health.
With `S3_BUCKET_NAME` empty, files are saved in `backend\data\files` (local mode, no AWS needed).

### 9.2 Frontend (terminal 2, click **+** in the terminal panel)
```powershell
cd frontend
npm install
copy .env.example .env                 # VITE_API_BASE_URL=http://localhost:8000
npm run dev
```
Open http://localhost:5173. Click **Human ubiquitin**, then **Submit prediction**.

### 9.3 Optional: use your real S3 bucket from your PC
Install the [AWS CLI](https://aws.amazon.com/cli/) and run `aws configure` with your own IAM user's
keys. The keys are saved in `%USERPROFILE%\.aws\credentials`, outside the project. Then set
`S3_BUCKET_NAME` and `AWS_REGION` in `backend\.env` and restart uvicorn. The AWS Cloud Status page will
show `credential_source: shared-credentials-file` locally, and `iam-role` on EC2.

## 10. Environment variables
| Variable | Where | Meaning |
|---|---|---|
| `AWS_REGION` | backend | Region of the S3 bucket (for example `us-east-1`) |
| `S3_BUCKET_NAME` | backend | Bucket for results. Empty means local-disk mode |
| `S3_PREFIX` | backend | Key prefix (default `jobs`). Must match the IAM policy resource |
| `STORAGE_BACKEND` | backend | `auto` (default), `s3` or `local` |
| `PRESIGNED_URL_EXPIRY_SECONDS` | backend | Lifetime of download links (default 900 = 15 min) |
| `CORS_ORIGINS` | backend | Comma-separated frontend origins allowed to call the API |
| `PREDICTION_ENGINE` | backend | `esmatlas` (default), `nvidia` (needs `NVIDIA_API_KEY`) or `none` |
| `DEMO_TASK_DELAY_SECONDS` | backend | Default artificial delay for C–G (0 = off) |
| `MAX_SEQUENCE_LENGTH` | backend | Default 400 (the ESM Atlas API limit) |
| `VITE_API_BASE_URL` | frontend | Backend URL. Empty means same server (nginx option) |

AWS access keys are **never** variables of this app. `VITE_*` values are compiled into public JavaScript.

## 11. REST API (all under `/api`; full docs at `/docs`)
| Method | Path | Description |
|---|---|---|
| POST | `/api/predict` | Body `{sequence, name?, execution_mode: "parallel"\|"sequential", demo_delay_seconds?}` → `202 {job_id}`. Invalid input → `422` with a message |
| GET | `/api/tasks/{job_id}` | Job status, progress %, every task's status/duration/error |
| GET | `/api/results/{job_id}` | Final report, metrics, stored-file records, storage warnings |
| GET | `/api/results/{job_id}/downloads` | Fresh download links (S3 presigned URLs, 15 min) |
| GET | `/api/results/{job_id}/structure` | Predicted PDB text, read from S3, for the 3D viewer |
| GET | `/api/files/{job_id}/{filename}` | Local-mode file download |
| GET | `/api/history` | Previous runs |
| DELETE | `/api/history/{job_id}` | Delete a run and its S3 objects |
| GET | `/api/health` | Status, S3 connectivity, credential source, prediction engine |
| POST | `/api/benchmark` | Runs C–G sequentially, then in parallel, and returns both timings |

### Example input / output
```
POST /api/predict
{"sequence": ">ubiquitin\nMQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG",
 "execution_mode": "parallel", "demo_delay_seconds": 1}
→ 202 {"job_id": "2187215668504c0ab1dc96f35ca41932", "status": "queued", ...}

GET /api/results/2187215668504c0ab1dc96f35ca41932   (abridged)
{"status": "completed", "total_seconds": 1.05,
 "metrics": {"parallel_stage_wall_seconds": 1.01, "parallel_stage_sum_seconds": 5.01, "speedup_vs_sum": 4.97},
 "report": {"length": 76,
   "analyses": {"D": {"molecular_weight_da": 8564.73, "isoelectric_point": 6.56, "stability_class": "stable", ...}},
   "structure": {"available": true, "engine": "ESMFold via Meta ESM Atlas API", "mean_plddt": ..., ...},
   "disclosures": ["Task C is an empirical ... NOT a 3D prediction.", ...]},
 "files": [{"filename": "report.json", "backend": "s3", "bucket": "...", "key": "jobs/2187.../report.json"}, ...]}
```

## 12. Testing
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -q          # 25 tests: validation, DAG ordering, parallel speed-up, API, S3 (moto), error handling
```
The full test plan (valid and invalid inputs, AWS checks) is in [docs/TESTING.md](docs/TESTING.md).

## 13. Deploy to AWS
Follow **[docs/AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md)**. It is a step-by-step guide: S3 bucket → IAM policy and
role → EC2 instance → backend service → connect the frontend → verify. Problems are covered in
**[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)**.

## 14. How the project demonstrates cloud computing
- **Web-based access:** any browser, with no local installation for users.
- **Client-server architecture:** React client and REST API server.
- **Centralised processing** on EC2, with GPU inference delegated to a remote ESMFold service.
- **Parallel execution:** six independent tasks run concurrently, with measured speed-up.
- **Persistent object storage:** S3 keeps results durably, independent of the server's disk.
- **Security:** IAM role with least privilege, presigned URLs, private bucket, strict CORS.
- **Configuration through environment variables:** the same code runs locally and on AWS.
- **Scalability path:** the stateless API could sit behind a load balancer with several EC2 instances or an
  Auto Scaling group, with SQS for job queueing and RDS/DynamoDB replacing SQLite.

## 15. Limitations and future work
- ESMFold is called over the internet. The public ESM Atlas API has had outages and accepts up to about 400 residues.
  Switch to `PREDICTION_ENGINE=nvidia` with a free key from build.nvidia.com, or host ESMFold on a GPU EC2 instance.
- Threads speed up I/O-bound work (the ESMFold call, the artificial delay) but not CPU-heavy Python, because of
  the GIL. Use `ProcessPoolExecutor`, AWS Batch or Lambda fan-out for heavy compute.
- SQLite and the in-process job queue suit one instance. Use RDS/DynamoDB and SQS to scale out.
- No BLAST search, user accounts or HTTPS by default. HTTPS needs a domain plus an ALB/ACM certificate or Let's Encrypt.
- Task C's Chou-Fasman estimate is a teaching method with limited accuracy.

## 16. Screenshots to capture for the report
1. Dashboard with the example sequence and the S3/engine status strip
2. Workflow page while C–H are running (parallel box all blue), then completed
3. Same sequence in **sequential** mode: the timeline shows bars one after another
4. Results page: 3D viewer coloured by pLDDT, and the downloads table showing "Amazon S3"
5. Performance page: benchmark bar chart (sequential ≈ 5 s vs parallel ≈ 1 s with a 1 s delay)
6. AWS Cloud Status page on EC2 showing `credential_source: iam-role` and host `ip-172-31-…`
7. AWS console: S3 bucket → `jobs/<id>/` objects; IAM role with its policy; EC2 instance with the role attached
8. A downloaded presigned URL in the browser address bar, showing `X-Amz-Expires=900`
9. An invalid sequence error message

See also [docs/VIVA_GUIDE.md](docs/VIVA_GUIDE.md) for viva questions and answers.
