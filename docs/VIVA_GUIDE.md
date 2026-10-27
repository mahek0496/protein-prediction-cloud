# Viva Guide

## 2-minute project explanation
"Our project is a cloud application for protein structure prediction. A user pastes a protein sequence into a
React website. The site sends it to a FastAPI backend running on an Amazon EC2 instance. The backend runs a
workflow of nine tasks. Task A validates the sequence. Task B turns it into a 31-number feature vector.
Tasks C to H are independent, so they run in parallel in a thread pool. Five of them are sequence analyses:
secondary-structure propensity, physicochemical properties, hydropathy, charge, and motifs. Task H sends the
sequence to ESMFold, a published deep-learning model from Meta, which returns a real predicted 3D structure
with per-residue confidence. Task I waits for all of them and builds the final report.

The report and the PDB/mmCIF structure files are uploaded to an Amazon S3 bucket with boto3. The EC2 instance
gets permission through an IAM role that can only read, write and delete objects under one folder of that
bucket, so no access keys exist anywhere. Users download files through presigned URLs that expire after 15
minutes. The app records how long every task takes and compares sequential and parallel execution. With five
one-second tasks we measured about 5 seconds sequentially versus about 1 second in parallel."

## Likely questions
**Why EC2 and not just your laptop?**
The server is reachable from anywhere, keeps running when the laptop is off, can be resized or replicated, and
gets AWS permissions through an IAM role instead of personal keys.

**Why S3 instead of saving files on EC2's disk?**
S3 is durable object storage, independent of the instance. Terminating or replacing the server does not lose
results. Several servers could share one bucket, and S3 supports secure, expiring download links.

**How does the app get AWS credentials?**
The IAM role is attached to the instance as an *instance profile*. EC2's metadata service hands out temporary
credentials that rotate automatically. boto3's default credential chain picks them up. The Cloud Status page
shows `credential_source = iam-role` as proof.

**What is a presigned URL?**
A normal S3 URL with a signature, made by the backend's credentials, and an expiry time in the query string.
Anyone holding it can download that one object until it expires. The bucket itself stays private.

**Why does the role need `s3:GetObject` if the user downloads the file?**
A presigned URL acts with the permissions of the identity that signed it. If the role can't `GetObject`, the URL is refused.

**What is least privilege here?**
Only `PutObject`/`GetObject`/`DeleteObject` on `bucket/jobs/*`, plus `ListBucket` on that one bucket. The role
cannot list other buckets, write elsewhere, or change bucket settings. We demonstrate that `aws s3 ls` fails on EC2.

**How do you make sure a task doesn't start too early?**
Our scheduler (`dag.py`) checks each task's `depends_on` list and submits it to the thread pool only when all
dependencies have finished. Tests assert that each task's start time is after its dependencies' end times.

**Threads in Python have the GIL. Why do you get a speed-up?**
The GIL blocks parallel *CPU* work in threads, but it is released while waiting on I/O and `sleep()`. Task H
waits on the network, and the demo delay is a sleep, so they overlap. The local analyses take milliseconds, so
with no delay the speed-up is about 1×, and we show that honestly. For CPU-heavy work we would use
`ProcessPoolExecutor` or several machines.

**Is the 3D structure real?**
Yes, when Task H succeeds. It comes from ESMFold, a published model. We show its pLDDT confidence and colour the
structure by it. It is still a prediction, not an experimental structure. If ESMFold is unavailable, we say
so and show no structure. We never fake coordinates.

**Is Chou-Fasman a structure prediction?**
No. It is a 1970s statistical propensity method, about 50–60% accurate per residue. We label it as an
*empirical estimate*, not a 3D prediction.

**What is pLDDT?**
Predicted Local Distance Difference Test, a 0–100 per-residue confidence. Above 90 is very high, 70–90 is
confident, 50–70 is low, and below 50 is very low (often disordered regions).

**What happens if S3 fails?**
boto3 errors are translated into clear messages (no credentials, access denied, no such bucket, wrong region,
unreachable). The file is saved on the server's disk instead, the job still completes, and the UI shows the warning.

**How would you scale this?**
Put several EC2 instances behind an Application Load Balancer, or use an Auto Scaling group. Move jobs to an SQS
queue processed by workers, replace SQLite with RDS or DynamoDB, host the frontend on S3 + CloudFront with HTTPS,
and run ESMFold on GPU instances or AWS Batch.

**What does CORS do here?**
Browsers block JavaScript from calling a different origin unless the server allows it. FastAPI's CORSMiddleware
allows only the origins in `CORS_ORIGINS`, such as `http://localhost:5173`. Other sites are refused.

## Parallel execution in one picture
```
Sequential (1 worker):  C█████ D█████ E█████ F█████ G█████          ≈ 5 × 1 s = 5 s
Parallel  (6 workers):  C█████
                        D█████
                        E█████   all start when B finishes           ≈ max(1 s) = 1 s
                        F█████
                        G█████
Speed-up = 5 s / 1 s ≈ 5×   (ideal for 5 equal, independent, I/O-bound tasks)
```
