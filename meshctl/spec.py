"""Validate a traffic spec and render the Istio resources it describes."""
import re

import yaml

DURATION = re.compile(r"^\d+(ms|s|m|h)$")
NAME = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
MTLS = {"STRICT", "PERMISSIVE", "DISABLE"}


def load(path):
    with open(path) as f:
        return yaml.safe_load(f)


def validate(spec):
    errors = []
    for key in ("service", "namespace", "port", "subsets"):
        if key not in spec:
            errors.append(f"missing {key}")
    if errors:
        return errors
    if not NAME.match(str(spec["service"])) or not NAME.match(str(spec["namespace"])):
        errors.append("service and namespace must be DNS labels")
    if not isinstance(spec["port"], int) or not 1 <= spec["port"] <= 65535:
        errors.append("port must be 1 to 65535")
    subsets = spec["subsets"]
    if not subsets:
        errors.append("subsets must not be empty")
    else:
        for name, weight in subsets.items():
            if not NAME.match(str(name)):
                errors.append(f"subset {name}: not a DNS label")
            if not isinstance(weight, int) or weight < 0 or weight > 100:
                errors.append(f"subset {name}: weight must be an integer from 0 to 100")
        if all(isinstance(w, int) for w in subsets.values()) and sum(subsets.values()) != 100:
            errors.append(f"weights add up to {sum(subsets.values())}, not 100")
    r = spec.get("retries")
    if r:
        if not 1 <= r.get("attempts", 0) <= 5:
            errors.append("retries.attempts must be 1 to 5 (more risks a retry storm)")
        if not DURATION.match(str(r.get("perTryTimeout", ""))):
            errors.append("retries.perTryTimeout must look like 2s")
    o = spec.get("outlier")
    if o:
        if o.get("consecutive5xx", 0) < 1:
            errors.append("outlier.consecutive5xx must be at least 1")
        if not 0 < o.get("maxEjectionPercent", 0) <= 100:
            errors.append("outlier.maxEjectionPercent must be 1 to 100")
        for k in ("interval", "baseEjection"):
            if not DURATION.match(str(o.get(k, ""))):
                errors.append(f"outlier.{k} must look like 30s")
    if spec.get("mtls", "STRICT") not in MTLS:
        errors.append(f"mtls must be one of {sorted(MTLS)}")
    return errors


def render(spec):
    """Return a list of Istio resource dicts: DestinationRule, VirtualService, PeerAuthentication."""
    svc, ns = spec["service"], spec["namespace"]
    meta = lambda kind, name: {"apiVersion": kind, "metadata": {"name": name, "namespace": ns}}  # noqa: E731
    traffic = {"tls": {"mode": "ISTIO_MUTUAL"}}
    if spec.get("outlier"):
        o = spec["outlier"]
        traffic["outlierDetection"] = {"consecutive5xxErrors": o["consecutive5xx"], "interval": o["interval"],
                                       "baseEjectionTime": o["baseEjection"], "maxEjectionPercent": o["maxEjectionPercent"]}
    dr = meta("networking.istio.io/v1", svc) | {"kind": "DestinationRule", "spec": {
        "host": svc, "trafficPolicy": traffic,
        "subsets": [{"name": n, "labels": {"version": n}} for n in spec["subsets"]]}}
    route = {"route": [{"destination": {"host": svc, "subset": n, "port": {"number": spec["port"]}}, "weight": w}
                       for n, w in spec["subsets"].items() if w > 0]}
    if spec.get("retries"):
        r = spec["retries"]
        route["retries"] = {"attempts": r["attempts"], "perTryTimeout": r["perTryTimeout"], "retryOn": r["retryOn"]}
    vs = meta("networking.istio.io/v1", svc) | {"kind": "VirtualService", "spec": {"hosts": [svc], "http": [route]}}
    pa = meta("security.istio.io/v1", "default") | {"kind": "PeerAuthentication",
                                                   "spec": {"mtls": {"mode": spec.get("mtls", "STRICT")}}}
    return [dr, vs, pa]


def to_yaml(resources):
    return yaml.safe_dump_all(resources, sort_keys=False)
