# service-mesh-lab

Istio on a local kind cluster, with a tool that checks a traffic spec before it is applied, a small web page for changing canary weights, and Gherkin scenarios that test real traffic.

It is for engineers who run or are learning a service mesh and want to see config changes tested against a cluster, not just linted. It is a small lab: one namespace, two echo services, no production traffic. The Jenkinsfile is included but was not run on a Jenkins server.

## Run it

Needs Docker, kind, kubectl, Python 3.10 or later. The first run downloads `istioctl` 1.24.2 and checks its checksum. About 6 minutes.

```bash
git clone https://github.com/gerardrecinto/service-mesh-lab.git && cd service-mesh-lab
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
bash scripts/e2e.sh        # ends with: 6 scenarios passed, ALL PASS
```

If kind cannot create the cluster, check `docker info`. The cluster needs about 2 GB of Docker memory; stop other kind clusters first. Remove the lab with `kind delete cluster --name mesh-lab`.

## What the scenarios check

1. A 90/10 spec sends a small share of 200 requests to v2.
2. `meshctl set-weights v1=50 v2=50` and apply moves the real split.
3. Weights that do not add up to 100 are refused and nothing changes.
4. A pod without a sidecar cannot call a service under STRICT mTLS; a pod in the mesh can.
5. A replica that always returns 500 is ejected by outlier detection, and the last 20 responses succeed.
6. Scaling a deployment to 3 replicas, sending 300 requests with no errors, and scaling back.

## The tool

`mesh/traffic.yaml` is the source of truth. `python -m meshctl validate|render|apply|set-weights|ui FILE`.

- Validation rejects weights that do not sum to 100, retries above 5 attempts, bad durations, and unknown mTLS modes.
- `render` prints a DestinationRule (subsets, outlier detection, mutual TLS), a VirtualService (weights, retries) and a PeerAuthentication.
- `ui` serves a one-page form on localhost that validates before it writes the file and applies it.

## Layout

```
meshctl/    spec validation and rendering, CLI, web page
mesh/       sample app, traffic specs, kind config
features/   Gherkin scenarios and steps (behave)
scripts/    e2e.sh
Jenkinsfile validate, analyze, staging with the scenarios, then promote behind an approval
```

## Limits

- Lab scale. Latency, throughput and multi-cluster behaviour are not tested.
- The share checks use wide bounds (3 to 20 percent for a 10 percent weight) because 200 requests is a small sample.
- The web page has no authentication and binds to 127.0.0.1 only.
- No Argo CD. Rollback is a revert of the spec and a rerun.
- The Jenkinsfile was not run.

MIT license.
