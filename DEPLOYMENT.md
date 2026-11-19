# AWS deployment guide (S3 + CloudFront for React, EC2 for FastAPI)

**Nothing in this guide has been run in your AWS account.** I (the assistant) cannot access it. What I did run is listed in
section 12. Everything marked **YOU** must be done by you in your account. Costs are not guaranteed to be zero (section 10).

## 1. Architecture and request flow

```
                    HTTPS (free CloudFront certificate, no domain needed)
Browser ───────────────────────────────▶ CloudFront  d1234abcd.cloudfront.net
                                           │
              default behavior (/*)        │         /api/*  behavior
        ┌──────────────────────────────────┴──────────────────────────────┐
        ▼  CloudFront Function: paths without "." -> /index.html          ▼  caching OFF, all HTTP methods
  S3 bucket (PRIVATE, access only via CloudFront OAC)              EC2 t3.micro, ap-south-1, Ubuntu 24.04
  React build: index.html + hashed assets                          security group: port 80 only from CloudFront
                                                                   nginx :80  (needs header X-Origin-Verify)
                                                                     └▶ uvicorn 127.0.0.1:8000 (systemd, auto-restart)
                                                                          └▶ FastAPI: model + JSON assets loaded once in memory
```
Why this design: one HTTPS origin for the browser (no CORS, no mixed-content problem), static files served by a CDN,
and one small server that only runs the API. The raw dataset never leaves your computer.

Options I considered and did not choose as the default: Lambda container + API Gateway (scales to zero but adds ECR, cold starts and
packaging risk for scikit-learn), App Runner / ECS Fargate (needs Docker and costs more), S3 website hosting + EC2 directly
(S3 website endpoints are HTTP only, so a browser would block the API calls).

**Known limitation:** the CloudFront → EC2 hop is plain HTTP (a CloudFront origin needs a trusted certificate for HTTPS, which means a
domain name). The data is non-sensitive aggregates and the origin only accepts CloudFront traffic with a secret header, which is
acceptable for a capstone demo but not for production.

## 2. What was verified about AWS (and what was not)

Verified from AWS documentation/announcements when this guide was written:
* Accounts created **on or after 15 July 2025** use the credit-based Free plan (USD 100 credits, up to 100 more through activities, ends after
  6 months or when credits run out, whichever is first). Accounts created **before** that date stay on the legacy Free Tier.
* CloudFront's always-free allowance: 1 TB data out and 10 million requests per month. CloudFront Functions: 2 million invocations per month.
* A public IPv4 address costs USD 0.005 per hour; the legacy EC2 free tier includes 750 hours/month of it for EC2 only.
* The CloudFront managed prefix list (`com.amazonaws.global.cloudfront.origin-facing`) counts as **55** rules; the default limit is **60**
  rules per security group, so keep that group to the CloudFront rule plus at most 4 others (this guide uses 2).

**Not verified, check yourself:** whether your account is legacy or credit-based (Billing console → Free Tier); whether `t3.micro` is offered and
marked "Free tier eligible" in `ap-south-1` for your plan (the launch wizard shows it; pick the eligible type it offers, but keep at least 1 GiB RAM);
current on-demand prices in Mumbai; that the prefix list exists in `ap-south-1` (command in step 5).

## 3. Production folder structure

`python deployment/build_release.py` creates `release/absenteeism-api-release.tar.gz` (about 0.6 MB):
```
absenteeism/                      (unpacked on the server, e.g. ~/absenteeism)
├── backend/__init__.py, backend/app/…, backend/requirements.txt
├── src/{__init__,config,predict,reason_codes,simulation}.py        runtime subset only
├── models/{absenteeism_pipeline.joblib, model_metadata.json, metrics.json}
├── reports/app_assets/{analytics,model_grid,evaluation}.json       aggregates only
└── deployment/{setup_ec2.sh, smoke_check.py, health_check.sh, *.template, …}
```
Not included, by design: `data/raw` (health-related personal data), notebooks, tests, training code, Streamlit, `.venv`, `node_modules`.
The frontend is built separately into `frontend/dist` and goes to S3.

## 4. Prerequisites on your computer (YOU)
* Python 3.12, Node 20+, the AWS CLI v2, and an SSH client.
* **Do not use root account keys.** Create an IAM user (or use IAM Identity Center) with permissions for S3, EC2, CloudFront and Budgets, then run
  `aws configure` (or `aws configure sso`). Credentials stay in `~/.aws`, never in this repository.
```bash
export AWS_REGION=ap-south-1
aws sts get-caller-identity            # confirms which account you are using
```

## 5. Create the EC2 security group and server (YOU)

**5.1 Find the CloudFront prefix list in Mumbai (also verifies it exists there):**
```bash
aws ec2 describe-managed-prefix-lists --region ap-south-1 \
  --query "PrefixLists[?PrefixListName=='com.amazonaws.global.cloudfront.origin-facing'].PrefixListId" --output text
# prints something like pl-xxxxxxxx   (empty output = not available in this region; see Troubleshooting)
```
**5.2 Create the security group** (console: EC2 → Security Groups → Create; or CLI):
```bash
VPC_ID=$(aws ec2 describe-vpcs --region ap-south-1 --filters Name=is-default,Values=true --query "Vpcs[0].VpcId" --output text)
SG_ID=$(aws ec2 create-security-group --region ap-south-1 --group-name absenteeism-api-sg \
  --description "Absenteeism API: HTTP from CloudFront, SSH from my IP" --vpc-id "$VPC_ID" --query GroupId --output text)
MY_IP=$(curl -s https://checkip.amazonaws.com)
aws ec2 authorize-security-group-ingress --region ap-south-1 --group-id "$SG_ID" \
  --ip-permissions "IpProtocol=tcp,FromPort=80,ToPort=80,PrefixListIds=[{PrefixListId=pl-xxxxxxxx}]" \
                   "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=${MY_IP}/32}]"
```
Replace `pl-xxxxxxxx` with the id from 5.1. **Do not open port 8000** (uvicorn listens on localhost only) and **never** open 22 to `0.0.0.0/0`.
If your IP changes, update the SSH rule.

**5.3 Launch the instance** (console: EC2 → Launch instance):
* Name `absenteeism-api`; AMI **Ubuntu Server 24.04 LTS**; instance type **t3.micro** (or the "Free tier eligible" type the wizard offers, ≥ 1 GiB RAM).
* Key pair: create a new one, download the `.pem`, then `chmod 400 absenteeism-key.pem`.
* Network: default VPC, **auto-assign public IP: enabled**, security group: the one from 5.2.
* Storage: 8–10 GiB gp3 is enough.
* After launch, copy the **Public IPv4 DNS** (like `ec2-13-xx-xx-xx.ap-south-1.compute.amazonaws.com`).
  CloudFront needs this DNS *name*, not the IP. The name changes if you stop and start the instance unless you attach an Elastic IP
  (which also costs USD 0.005/hour); simplest is to leave the instance running during the demo window and update the CloudFront origin if it changes.

## 6. Build and install the backend

On your computer:
```bash
python deployment/build_release.py            # also runs `npm ci` and `npm run build` for the frontend
scp -i absenteeism-key.pem release/absenteeism-api-release.tar.gz ubuntu@<EC2_PUBLIC_DNS>:~/
```
On the server (`ssh -i absenteeism-key.pem ubuntu@<EC2_PUBLIC_DNS>`):
```bash
mkdir -p ~/absenteeism && tar xzf absenteeism-api-release.tar.gz -C ~/absenteeism
cd ~/absenteeism && bash deployment/setup_ec2.sh
```
The script: checks the files, installs `python3-venv nginx curl`, creates `.venv` and installs the pinned runtime requirements, runs an offline
smoke test of the saved model, adds a 1 GB swap file if there is none, generates a random **origin secret** (stored in `/etc/absenteeism/origin_secret`,
root-only), installs the nginx site and the `absenteeism-api` systemd service (restarts automatically on failure and on reboot), and waits for the health check.
**At the end it prints the secret header value. Copy it for step 7.** You can re-run the script safely.

Check on the server:
```bash
bash deployment/health_check.sh http://127.0.0.1            # HEALTHY {"status":"ok","model_loaded":true,...}
.venv/bin/python deployment/smoke_check.py --url http://127.0.0.1:8000
sudo systemctl status absenteeism-api --no-pager
```
Optional environment settings go in `/etc/absenteeism/api.env` (e.g. `LOG_LEVEL=INFO`), then `sudo systemctl restart absenteeism-api`.
`CORS_ORIGINS` is not needed because CloudFront makes browser requests same-origin.

## 7. S3 bucket and CloudFront (YOU)

**7.1 Bucket** (names are global; choose your own):
```bash
export BUCKET=absenteeism-site-<your-name>-<random>
aws s3api create-bucket --bucket $BUCKET --region ap-south-1 --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api put-public-access-block --bucket $BUCKET --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```
**7.2 CloudFront function** (console: CloudFront → Functions → Create function, runtime `cloudfront-js-2.0`): paste
`deployment/cloudfront-spa-rewrite.js`, Save, **Publish**.

**7.3 Distribution** (console: CloudFront → Create distribution → **Free plan** or pay-as-you-go as offered; check what your console shows):
1. **Origin 1:** Amazon S3 → your bucket; Origin access: **Origin access control (OAC)**, create a new one. When the console offers the bucket policy,
   copy and apply it to the bucket (this is what makes the private bucket readable by CloudFront only).
2. **Default behavior:** viewer protocol *Redirect HTTP to HTTPS*; allowed methods GET, HEAD; cache policy *CachingOptimized*;
   **Function associations → Viewer request → the function from 7.2**.
3. **Default root object:** `index.html`.
4. **Add origin 2:** Custom → Origin domain = the EC2 **Public IPv4 DNS**; protocol **HTTP only**, HTTP port **80**;
   **Add custom header** `X-Origin-Verify` = the value printed by `setup_ec2.sh`.
5. **Add behavior:** path pattern `/api/*`; origin = the EC2 origin; viewer protocol *Redirect HTTP to HTTPS*;
   allowed methods **GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE** (POST is required); cache policy **CachingDisabled**;
   origin request policy **AllViewerExceptHostHeader**.
6. Do **not** add custom error pages for 403/404 (they are distribution-wide and would turn API errors into HTML; the function handles deep links).
7. Create, wait until the status is *Deployed* (a few minutes), and note the domain `dxxxxxxxx.cloudfront.net` and the distribution ID.

**7.4 Upload the frontend:**
```bash
BUCKET=$BUCKET DISTRIBUTION_ID=E123ABC456 bash deployment/deploy_frontend.sh
```

## 8. End-to-end verification checklist

Replace `DOMAIN` with your CloudFront domain.
- [ ] `curl -s https://DOMAIN/api/health` → `{"status":"ok","model_loaded":true,...}`
- [ ] `python deployment/smoke_check.py --url https://DOMAIN` → `SMOKE TEST PASSED` (works through CloudFront, so it also proves the secret header and security group)
- [ ] `curl -s -o /dev/null -w "%{http_code}\n" http://<EC2_PUBLIC_DNS>/api/meta` from your laptop → **timeout or 403** (the server must not be directly reachable)
- [ ] Open `https://DOMAIN/` → Home shows 697 events, 33 employees, v1.0.0
- [ ] Open `https://DOMAIN/predict` directly in a new tab (deep link works) and predict reason 23 / July / Tuesday → "Likely a short absence"; reason 22 → "Likely a long absence"
- [ ] Data Explorer, Model Performance, Insights and About load charts without an error banner
- [ ] Workforce Planning: **Run scenarios** shows the comparison, a disclaimer and Monte Carlo rows
- [ ] Submit an invalid scenario (headcount 0) → field error, no request sent
- [ ] Browser DevTools → Network: calls go to `/api/...` on the same domain, status 200, no CORS errors
- [ ] `sudo reboot` the server, wait 1–2 minutes, `curl https://DOMAIN/api/health` → healthy again (proves auto-start)
- [ ] Billing → Free Tier / Budgets shows no unexpected usage

## 9. Operations

| Task | Command (on the server unless stated) |
|---|---|
| API logs | `sudo journalctl -u absenteeism-api -f` |
| nginx logs | `sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log` |
| Restart API / nginx | `sudo systemctl restart absenteeism-api` / `sudo systemctl reload nginx` |
| Health | `bash deployment/health_check.sh http://127.0.0.1` |
| Memory | `free -m; ps -o rss,cmd -C python` (the API used about 210 MB when tested locally) |
| Deploy a new backend | rebuild, `scp` the archive, unpack over `~/absenteeism`, `bash deployment/setup_ec2.sh` |
| Deploy a new frontend | `npm run build` then `deploy_frontend.sh` (your computer) |
| Read the origin secret again | `sudo cat /etc/absenteeism/origin_secret` |

## 10. Cost safeguards (YOU, do these before launching anything)
1. **Billing → Budgets → Create budget → Zero spend budget** (or a USD 5 monthly cost budget) with e-mail alerts.
2. Billing → Billing preferences → turn on **Free Tier usage alerts** and billing alerts.
3. Know your plan: credit-based Free plan accounts spend credits and expire after 6 months or when credits run out; legacy accounts have 12-month EC2 hours.
   Either way, a public IPv4 address, data transfer beyond limits, Elastic IPs and snapshots can create charges.
4. Run only one instance, no NAT gateway, no load balancer, no RDS (none are needed).
5. Set a calendar reminder to run the teardown below right after your demonstration.

Rough expectation, not a promise: CloudFront and S3 usage for a capstone is far below the always-free CloudFront limits; the EC2 instance and its public IPv4
address are the only items that can cost money if your plan does not cover them (IPv4 alone is about USD 0.005 per hour while in use). Check the current
Mumbai prices on the EC2 pricing page before leaving it running for weeks.

## 11. Stop or delete everything after the demonstration (YOU)
```bash
# 1. CloudFront: disable first (console: select the distribution -> Disable), wait until "Deployed", then delete it
aws cloudfront list-distributions --query "DistributionList.Items[].{id:Id,domain:DomainName,enabled:Enabled}"
# 2. S3: empty and delete the bucket
aws s3 rm s3://$BUCKET --recursive && aws s3api delete-bucket --bucket $BUCKET --region ap-south-1
# 3. EC2: terminate the instance (console: Instance state -> Terminate), then release any Elastic IP you allocated
aws ec2 terminate-instances --region ap-south-1 --instance-ids i-xxxxxxxxxxxxxxxxx
aws ec2 describe-addresses --region ap-south-1          # should be empty
# 4. After the instance is terminated: delete the security group and the key pair
aws ec2 delete-security-group --region ap-south-1 --group-id $SG_ID
aws ec2 delete-key-pair --region ap-south-1 --key-name absenteeism-key
# 5. Delete the CloudFront function and origin access control (console), then check Billing -> Bills the next day
```
**Stopping** (instead of terminating) the instance stops compute charges but its public DNS name changes when restarted, and attached storage still bills.

## 12. What I actually ran vs what you must run

Run by me, in a sandbox, with real results:
`python -m pytest` (141 passed), frontend `npm test` (22 passed, 7 live tests skipped by default), the live-API frontend tests (7 passed against a real server),
`npm run build` (succeeded), `build_release.py --skip-frontend`, `SKIP_SYSTEMD=1 bash deployment/setup_ec2.sh` from the unpacked archive (passed),
`smoke_check.py --url` against a local uvicorn started from that archive (all checks passed), `bash -n` syntax checks of the shell scripts, and **the nginx config**: with the Ubuntu 24.04 package (nginx 1.24) `nginx -t` passed, and in front of the packaged API it returned 403 without the secret header, 200 with it (health, meta, predict, simulate), the normal 422 error body for invalid input, and 413 for a 100 KB body.

**Not run by me:** anything on AWS; the nginx configuration *on EC2* (it was tested locally, see above; `setup_ec2.sh` also runs `nginx -t` and stops if it fails);
the systemd unit; CloudFront behaviors; real-browser rendering (no browser was available).

## 13. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Home page shows "Could not load this section" | `/api` not routed: check the `/api/*` behavior exists, uses the EC2 origin, allows POST, and caching is disabled. Test `curl https://DOMAIN/api/health`. |
| `/api/...` returns **403** | The `X-Origin-Verify` value in CloudFront does not match `/etc/absenteeism/origin_secret`. Re-copy it, wait for the distribution to redeploy. |
| `/api/...` returns **502/504** | Origin unreachable: security group lacks the CloudFront prefix list on port 80, the CloudFront origin DNS is stale (instance was stopped/started), or the service is down (`systemctl status absenteeism-api`). |
| `/predict` deep link shows an XML "AccessDenied" error | The CloudFront Function is not published or not attached to the default behavior's *viewer request*. |
| Old frontend still shows after deploying | Invalidate `/index.html` (the script does) and hard refresh. |
| Security group rule fails: "maximum number of rules" | The prefix list weighs 55 of a default 60: use a fresh group with only the 2 rules above, or request a quota increase in Service Quotas. |
| Prefix list command prints nothing in `ap-south-1` | Check the region spelling and CLI version. If it truly does not exist, temporarily allow port 80 from `0.0.0.0/0` (the origin secret header still blocks direct use) and tell your instructor why. |
| API crashes or restarts repeatedly | `journalctl -u absenteeism-api -n 100`; check memory with `free -m` (swap should be on); confirm Python packages match `backend/requirements.txt` (scikit-learn must be 1.5.2). |
| `ModelLoadError` in logs | Files missing or a different scikit-learn version than the one that created the model. Re-run `setup_ec2.sh`. |
| `curl http://127.0.0.1/health` fails but port 8000 works | nginx problem: `sudo nginx -t`, `sudo systemctl status nginx`. |
| SSH timeout | Your IP changed: update the port 22 rule. |
