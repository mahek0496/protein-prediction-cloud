# AWS Deployment Guide (EC2 + S3 + IAM), for beginners on Windows

This guide shows how to put the application on AWS. You create **real** AWS resources in **your**
account. The code, the S3 logic and the IAM policy have been tested against an S3 emulator, but none of
these resources exist until you follow the steps below. Tick each verification step so you can prove the
deployment works.

**Placeholders used below** (replace them everywhere):

| Placeholder | Example |
|---|---|
| `YOUR-BUCKET-NAME` | `protein-results-surya-2026` (lowercase, globally unique) |
| `YOUR-REGION` | `us-east-1` (use the same region for S3 and EC2) |
| `EC2-PUBLIC-IP` | `3.85.120.45` (shown on the EC2 instance page) |
| `protein-key.pem` | the key-pair file you download in Step 4 |

> Cost note: use a free-tier-eligible instance type if your account offers one (check *Billing → Free Tier*).
> Stop or terminate the instance and empty the bucket when you are finished (Step 12).
> Setting a billing alarm in *Billing → Budgets* is a good idea.

---

## Step 1: Create the S3 bucket
1. Sign in to the AWS Console. Pick **YOUR-REGION** in the top-right region menu.
2. Open **S3** → **Create bucket**.
3. **Bucket type:** General purpose. **Bucket name:** `YOUR-BUCKET-NAME`.
4. **Object Ownership:** *ACLs disabled (recommended)*.
5. **Block Public Access:** leave **Block all public access** **ON**. Users download through presigned
   URLs, so the bucket never needs to be public.
6. **Default encryption:** SSE-S3 (the default).
7. Click **Create bucket**.
8. *(Optional)* To delete old results automatically, open the bucket → **Management** → **Create lifecycle rule**.
   Set prefix `jobs/` and *Expire current versions after 30 days*.

No bucket policy and no bucket CORS configuration are needed. The browser opens presigned links as normal
downloads and never calls S3 with JavaScript.

## Step 2: Create a least-privilege IAM policy
1. Open **IAM** → **Policies** → **Create policy** → **JSON** tab.
2. Paste the contents of `deploy/iam-policy.json`, replacing **both** occurrences of `YOUR-BUCKET-NAME`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "CheckBucketAndListAppPrefix", "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME" },
    { "Sid": "ReadWriteDeleteAppObjectsOnly", "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/jobs/*" }
  ]
}
```
3. **Next** → name it `ProteinAppS3Policy` → **Create policy**.

### Why each permission is needed (and nothing more)
| Permission | Resource | Used by the app for |
|---|---|---|
| `s3:PutObject` | `bucket/jobs/*` | Uploading `report.json`, `report.md`, `structure.pdb`, `structure.cif` after each job |
| `s3:GetObject` | `bucket/jobs/*` | Reading the PDB for the 3D viewer. **Also required to sign presigned download URLs:** a presigned URL only works if the identity that signed it may perform `GetObject` |
| `s3:DeleteObject` | `bucket/jobs/*` | Deleting a run's files from the History page |
| `s3:ListBucket` | the bucket itself | `HeadBucket` health check on the AWS Cloud Status page. It also makes S3 answer *404 Not Found* instead of *403 Access Denied* for missing files |

**Not granted:** listing all buckets (`s3:ListAllMyBuckets`), writing outside `jobs/`, changing bucket
settings or policies, or access to any other AWS service. If the server were compromised, the attacker
could only touch this app's `jobs/` folder.

## Step 3: Create the IAM role for EC2
1. **IAM** → **Roles** → **Create role**.
2. **Trusted entity type:** AWS service. **Use case:** **EC2** → **Next**.
   (This creates the trust policy in `deploy/ec2-trust-policy.json`, which lets EC2 instances assume the role.)
3. Search for and tick **ProteinAppS3Policy** → **Next**.
4. **Role name:** `ProteinAppEC2Role` → **Create role**.

How it works: when the role is attached to an instance, EC2 publishes short-lived, auto-rotating
credentials through the instance metadata service. boto3's default credential chain finds them by
itself, so the code contains no keys and `.env` contains no keys.

## Step 4: Launch the EC2 instance
1. **EC2** → **Launch instance**.
2. **Name:** `protein-backend`.
3. **AMI:** **Amazon Linux 2023** (64-bit x86).
4. **Instance type:** `t3.micro`, or another free-tier-eligible type. ESMFold runs remotely, so a small instance is enough.
5. **Key pair:** **Create new key pair** → name `protein-key`, type RSA, format **.pem** → it downloads.
   Move it to `C:\Users\<you>\.ssh\protein-key.pem`.
6. **Network settings** → **Edit** → *Create security group* named `protein-sg` with these inbound rules:

| Type | Port | Source | Why |
|---|---|---|---|
| SSH | 22 | **My IP** | You connect to the server |
| Custom TCP | 8000 | **My IP** | *Option A*: your browser calls FastAPI directly |
| HTTP | 80 | My IP (or Anywhere to share) | *Option B*: nginx serves the site |

   Outbound: leave **All traffic** (needed for S3, ESMFold and package installs).
7. **Advanced details** → **IAM instance profile** → choose **ProteinAppEC2Role**. ← *the key step*
   (Leave *Metadata version* as *V2 only (token required)*. boto3 supports it.)
8. **Launch instance**, then open the instance and copy its **Public IPv4 address** (`EC2-PUBLIC-IP`).

> If you forgot step 7: select the instance → **Actions → Security → Modify IAM role** → choose
> `ProteinAppEC2Role` → **Update IAM role**. No reboot is needed.

## Step 5: Connect to the instance
**Easiest:** select the instance → **Connect** → **EC2 Instance Connect** → **Connect** (opens a browser terminal).

**Or from Windows PowerShell:**
```powershell
# one-time: restrict the key file's permissions or ssh will refuse it
icacls "$env:USERPROFILE\.ssh\protein-key.pem" /inheritance:r
icacls "$env:USERPROFILE\.ssh\protein-key.pem" /grant:r "$($env:USERNAME):(R)"

ssh -i "$env:USERPROFILE\.ssh\protein-key.pem" ec2-user@EC2-PUBLIC-IP
```

**Check the role is attached** (on EC2):
```bash
aws sts get-caller-identity
# Expected: "Arn": "arn:aws:sts::123456789012:assumed-role/ProteinAppEC2Role/i-0abc..."
```

## Step 6: Upload the backend code to EC2
**Option 1: from your PC with scp** (PowerShell, in the project folder):
```powershell
tar -czf upload.tar.gz --exclude=node_modules --exclude=.venv --exclude=data --exclude=.env --exclude=__pycache__ backend deploy
scp -i "$env:USERPROFILE\.ssh\protein-key.pem" upload.tar.gz ec2-user@EC2-PUBLIC-IP:~
```
Then on EC2:
```bash
mkdir -p ~/protein-prediction-cloud && tar -xzf ~/upload.tar.gz -C ~/protein-prediction-cloud
```
**Option 2: from GitHub** (if you pushed the project there): `sudo dnf install -y git && git clone https://github.com/<you>/protein-prediction-cloud.git`

## Step 7: Install and configure the backend (on EC2)
```bash
cd ~/protein-prediction-cloud
bash deploy/setup_ec2.sh          # installs Python 3.11, creates .venv, installs requirements, copies .env
nano backend/.env                 # edit the values below, then Ctrl+O, Enter, Ctrl+X
```
Set:
```ini
APP_ENV=aws
AWS_REGION=YOUR-REGION
S3_BUCKET_NAME=YOUR-BUCKET-NAME
S3_PREFIX=jobs
STORAGE_BACKEND=s3
PRESIGNED_URL_EXPIRY_SECONDS=900
# Option A (frontend on your PC):  http://localhost:5173
# Option B (nginx on EC2):         http://EC2-PUBLIC-IP
CORS_ORIGINS=http://localhost:5173
PREDICTION_ENGINE=esmatlas
```
**Never** add `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` here. If they are set, boto3 would use them instead of the role.

**Quick test before making it a service:**
```bash
cd ~/protein-prediction-cloud/backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
# In the log, look for:  Storage backend: s3 | ok=True | Connected to S3 bucket '...'
```
In a second terminal (or after pressing Ctrl+C), run `curl -s localhost:8000/api/health`. Check for
`"backend":"s3"`, `"ok":true` and `"credential_source":"iam-role"`.

## Step 8: Run the backend as a service (survives logout and reboot)
```bash
sudo cp ~/protein-prediction-cloud/deploy/protein-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now protein-api
sudo systemctl status protein-api        # should say active (running)
journalctl -u protein-api -f             # live logs (Ctrl+C to exit)
```
From your PC, open `http://EC2-PUBLIC-IP:8000/api/health` and `http://EC2-PUBLIC-IP:8000/docs`.

## Step 9: Connect the React frontend
### Option A: frontend runs on your PC, backend on EC2 (simplest)
1. In `frontend\.env` set `VITE_API_BASE_URL=http://EC2-PUBLIC-IP:8000`.
2. Make sure the EC2 `.env` has `CORS_ORIGINS=http://localhost:5173` (then `sudo systemctl restart protein-api`).
3. `cd frontend; npm run dev` → open http://localhost:5173 → **AWS Cloud Status** page.

### Option B: everything on EC2 behind nginx (port 80)
1. On your PC, build with an **empty** API URL so the site calls its own server:
```powershell
cd frontend
Set-Content .env.production "VITE_API_BASE_URL="
npm run build
scp -i "$env:USERPROFILE\.ssh\protein-key.pem" -r dist ec2-user@EC2-PUBLIC-IP:~/frontend-dist
```
2. On EC2:
```bash
sudo dnf install -y nginx
sudo mkdir -p /usr/share/nginx/protein && sudo cp -r ~/frontend-dist/* /usr/share/nginx/protein/
sudo cp ~/protein-prediction-cloud/deploy/nginx-protein.conf /etc/nginx/conf.d/protein.conf
sudo nginx -t && sudo systemctl enable --now nginx && sudo systemctl reload nginx
# keep FastAPI private behind nginx:
sudo sed -i 's/--host 0.0.0.0/--host 127.0.0.1/' /etc/systemd/system/protein-api.service
sudo systemctl daemon-reload && sudo systemctl restart protein-api
```
3. Set `CORS_ORIGINS=http://EC2-PUBLIC-IP` in `backend/.env` and restart the service. Then open `http://EC2-PUBLIC-IP`.
   You can now remove the port-8000 rule from the security group.

> Amazon Linux 2023 ships its own default nginx server block. Our file marks itself `default_server`, so it
> should win. If `nginx -t` reports *duplicate default server*, or you still see the nginx welcome page, run
> `sudo nano /etc/nginx/nginx.conf`, delete the `server { ... }` block inside `http { }`, then run
> `sudo nginx -t && sudo systemctl reload nginx`.

## Step 10: Verify the deployment (evidence for your report)
- [ ] **AWS Cloud Status** page shows: Storage *Amazon S3*, your bucket, **Credential source `iam-role`**, host `ip-172-31-…`.
- [ ] Submit the ubiquitin example. The workflow completes, and the *S3* node and task show "Stored 4 file(s) in S3".
- [ ] S3 console → bucket → `jobs/<job-id>/` contains `report.json`, `report.md`, `structure.pdb`, `structure.cif`
      (the last two only if ESMFold was reachable).
- [ ] Results → **Download** works. The URL contains `X-Amz-Expires=900` and `X-Amz-Signature`. After 15 minutes,
      the same URL returns *AccessDenied / Request has expired*. Click **Refresh links** for new ones.
- [ ] Paste a download URL in a private window. It works without logging in, which shows that the URL itself carries the temporary authorisation.
- [ ] Least privilege, on EC2:
```bash
aws s3 ls s3://YOUR-BUCKET-NAME/jobs/                     # works (ListBucket)
aws s3 ls                                                  # AccessDenied (ListAllMyBuckets not granted)
echo hi > t.txt && aws s3 cp t.txt s3://YOUR-BUCKET-NAME/other/t.txt   # AccessDenied (outside jobs/)
```
- [ ] History → **Delete** removes the run and its S3 objects.

## Step 11: Things that change
- **The public IP changes when you stop and start the instance.** Update `VITE_API_BASE_URL` and
  `CORS_ORIGINS`, or allocate an **Elastic IP** (EC2 → Elastic IPs → Allocate → Associate). Note that an
  Elastic IP may be billed.
- **Code updates:** re-upload (Step 6), run `.venv/bin/pip install -r requirements.txt` if requirements
  changed, then `sudo systemctl restart protein-api`.
- **Different prediction engine:** set `PREDICTION_ENGINE=nvidia` and `NVIDIA_API_KEY=...` (from build.nvidia.com)
  in `backend/.env`, or `PREDICTION_ENGINE=none` to disable 3D prediction honestly.

## Step 12: Clean up after grading
1. EC2 → select the instance → **Instance state → Terminate**. Release any Elastic IP.
2. S3 → bucket → **Empty**, then **Delete**.
3. IAM → delete role `ProteinAppEC2Role` and policy `ProteinAppS3Policy` (optional, they are free).
4. EC2 → Security Groups → delete `protein-sg`. Key Pairs → delete `protein-key`.
