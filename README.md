# Sentinel

**A self-built, Kubernetes-native uptime monitoring and incident notification platform** — a small-scale UptimeRobot/Statuspage.io, designed from scratch as an end-to-end DevOps/SRE learning project covering the full lifecycle: containerization, orchestration, infrastructure as code, GitOps, CI, and observability.

Sentinel periodically checks a set of URLs, stores historical results in PostgreSQL, publishes real-time alerts through Redis pub/sub when a service goes down, sends email notifications, exposes a public JSON API and status page, and monitors its own health with Prometheus and Grafana.

---

## Why this project exists

Most portfolio projects stop at "I deployed a container." Sentinel goes further: it's a multi-service distributed system where every architectural decision (StatefulSet vs. Deployment, Terraform vs. GitOps, black-box vs. white-box monitoring) was made deliberately, and every component was built to answer a real operational question — "is my service up," "who gets paged," "who's watching the watcher."

---

## Architecture

```
                     ┌────────────────────┐
                     │   Status Page (JS)  │
                     └──────────┬──────────┘
                                │
                     ┌──────────▼──────────┐
                     │   Core API (FastAPI) │───/metrics──▶ Prometheus ──▶ Grafana
                     └──────────┬──────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                                    ▼
      ┌───────────────┐                   ┌────────────────┐
      │ Checker Worker │──publish(alert)─▶│  Redis (pub/sub) │
      │  (periodic)    │                   └────────┬────────┘
      └───────┬────────┘                            │
              │                            ┌─────────▼─────────┐
              ▼                            │  Notifier Worker    │──▶ Email (SMTP)
      ┌───────────────┐                    └────────────────────┘
      │  PostgreSQL     │
      │  (StatefulSet)  │
      └───────────────┘
```

Every service is stateless (checker, api, notifier) except PostgreSQL, which runs as a `StatefulSet` with a `PersistentVolumeClaim` so check history survives pod restarts. Services discover each other exclusively through Kubernetes DNS (`postgres`, `redis`, `sentinel-api`) — no hardcoded IPs anywhere.

---

## Features

- **Periodic health checks** against any set of URLs, with configurable interval
- **Persistent history** in PostgreSQL — status, HTTP code, response time, error, timestamp
- **Real-time alerting** via Redis pub/sub — checker publishes, notifier subscribes and emails
- **Public JSON API** (`/status`) and a live-updating **status page**
- **Self-observability** — a `/metrics` endpoint (Prometheus client) tracks the platform's own request volume, scraped by an in-cluster Prometheus and visualized in Grafana
- **Infrastructure as code** — Kubernetes resources for the platform's cluster-level building blocks are Terraform-managed (`kubernetes` provider)
- **GitOps deployment** — application manifests (`k8s/`) are the single source of truth, continuously reconciled by ArgoCD (`automated`, `selfHeal`, `prune`)
- **CI** — GitHub Actions builds all three service images (`checker`, `api`, `notifier`) on every push via a build matrix

---

## Tech stack

| Layer | Technology |
|---|---|
| Application | Python, FastAPI, `requests`, `psycopg2`, `redis-py`, `prometheus-client` |
| Data | PostgreSQL, Redis |
| Containers | Docker (per-service Dockerfiles) |
| Orchestration | Kubernetes (`kind` for local development) |
| IaC | Terraform (`hashicorp/kubernetes` provider) |
| GitOps | ArgoCD |
| CI | GitHub Actions |
| Observability | Prometheus, Grafana |
| Ingress | ingress-nginx |

---

## Project structure

```
sentinel/
├── checker.py              # periodic health-check worker
├── api.py                  # FastAPI service: /status, /metrics, static status page
├── notfier.py               # Redis subscriber → email notifications
├── static/                 # status page (HTML/CSS/JS)
├── requirements.txt
├── Dockerfile.checker
├── Dockerfile.api
├── Dockerfile.notifier
├── build-and-load.sh       # local build + kind load helper
├── k8s/                    # GitOps source of truth (watched by ArgoCD)
│   ├── config.yaml           # ConfigMap + Secret
│   ├── postgres.yaml          # StatefulSet + headless Service + readiness probe
│   ├── redis-deployment.yaml
│   ├── checker.yaml
│   ├── api.yaml                # Deployment + Service + Ingress
│   ├── notifier.yaml
│   └── prometheus.yaml / grafana.yaml
├── terraform/               # cluster-level infra (Terraform-managed)
│   ├── main.tf
│   └── variables.tf          # sensitive values injected via terraform.tfvars (gitignored)
├── argocd-app.yaml           # ArgoCD Application definition
└── .github/workflows/build.yml
```

---

## Running it locally

**Prerequisites:** Docker, `kind`, `kubectl`, Terraform, Python 3.12+

```bash
# 1. Spin up a local cluster
kind create cluster

# 2. Install ingress-nginx (kind-specific manifest)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# 3. Build and load service images
./build-and-load.sh

# 4. Install ArgoCD and point it at k8s/
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f argocd-app.yaml

# 5. Access the status page (after port-forwarding ingress-nginx)
kubectl port-forward -n ingress-nginx service/ingress-nginx-controller 8080:80
curl http://sentinel.local:8080/status
```

Set `sentinel.local` to `127.0.0.1` in `/etc/hosts` first.

---

## Roadmap

| Version | Milestone | Status |
|---|---|---|
| v0.1 | Checker + PostgreSQL + status API | ✅ |
| v0.2 | Static status page | ✅ |
| v0.3 | Redis pub/sub + email notifications | ✅ |
| v0.4 | Full stack deployed to Kubernetes (kind) | ✅ |
| v0.5 | Infrastructure as code (Terraform) | ✅ |
| v0.6 | CI — automated image builds (GitHub Actions) | ✅ |
| v0.7 | GitOps — continuous deployment via ArgoCD | ✅ |
| v0.8 | Self-observability (Prometheus + Grafana) | ✅ |
| v1.0 | Deploy to AWS EKS (Terraform `aws` provider, ECR) | 🔜 |

---

## What this project demonstrates

- Designing a multi-service system with correct service-discovery patterns (Kubernetes DNS, headless Services for StatefulSets)
- Choosing the right workload type per component (Deployment vs. StatefulSet) based on state requirements
- Separating cluster-level infrastructure (Terraform) from application deployment (GitOps) — a real architectural distinction, not just tooling preference
- Building health checks (`readinessProbe`) to solve real startup-ordering race conditions
- Instrumenting an application for observability from the inside, not just monitoring it from the outside

---

## License

MIT