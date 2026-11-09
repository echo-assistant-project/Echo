---
name: cloud-devops-basics
description: Run software reliably — the command line, git, servers, cloud basics (AWS/Azure/Google Cloud), Docker, deployments, monitoring and costs. Use for "deploy my app", "set up a server", "what is the cloud", "my server is down", "reduce my cloud bill", "learn Linux commands".
audience: developers
field: Technology
courses: The Missing Semester of Your CS Education (MIT) | https://missing.csail.mit.edu/ ; AWS Cloud Practitioner Essentials (AWS Skill Builder) | https://skillbuilder.aws/ ; Microsoft Learn: Azure Fundamentals (AZ-900) path | https://learn.microsoft.com/training/ ; Google Cloud Skills Boost | https://www.cloudskillsboost.google/
source: Echo (written for Echo from these courses' syllabi)
license: same as Echo
---

# Cloud and DevOps basics

## 1. The command line
Navigate (`cd`, `ls`/`dir`), files (`cp`, `mv`, `rm` — no undo!), search (`grep`/`Select-String`), processes (`ps`, `top`, Task Manager), pipes and redirection. Learn your shell's history search (Ctrl+R) and tab completion.

## 2. Git, the safety net
Commit small, meaningful changes; branch for features; pull before push; never commit secrets (`.env` in `.gitignore`); write messages that say *why*.

## 3. Servers and the cloud
- The cloud is renting computers, storage and services by the hour. Core building blocks: virtual machines (EC2 / Azure VM / Compute Engine), object storage (S3 / Blob / Cloud Storage), managed databases, serverless functions.
- Shared responsibility: the provider secures the data centre; you secure your accounts, data, configuration and code.
- Start with the smallest instance; use regions near your users (Mumbai/Hyderabad for India).

## 4. Containers
Docker packages an app with its dependencies: write a `Dockerfile`, build an image, run a container; `docker compose` for app + database. Pin versions; don't run as root; keep images small.

## 5. Deploying without fear
Automate with CI/CD (build, test, then deploy on merge). Keep configuration in environment variables, secrets in a secrets manager. Deploy small changes often; keep a one-command rollback; take database backups before migrations.

## 6. Monitoring and incidents
Watch: is it up (uptime check), how fast (latency), how many errors, how full (CPU, memory, disk). Alert only on things a person must act on. During an incident: stabilise first (roll back), then find the cause, then write a short blameless note.

## 7. Costs and security
Set a billing alert on day one; turn off idle machines; use free tiers carefully; lock the root account with 2FA and use separate users with least privilege; close unused ports; never expose databases to the internet. Private tools (home/office only) should stay on the local network or behind a VPN.
