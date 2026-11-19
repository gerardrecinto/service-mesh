import os
import shutil
import subprocess
import time

from behave import given, then, when

PY = os.environ.get("PYTHON", "python3")


def sh(cmd, check=True):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise AssertionError(f"{cmd}\n{r.stdout}\n{r.stderr}")
    return r


def mesh_curl(url, n, sleep=0):
    """Run n requests from the in-mesh client and return a list of (code, body)."""
    pause = f"sleep {sleep};" if sleep else ""
    loop = f"for i in $(seq {n}); do curl -s -m 5 -w '|%{{http_code}}' http://{url}/ | tr -d '\\n'; echo; {pause} done"
    r = subprocess.run(["kubectl", "-n", "shop", "exec", "deploy/client", "-c", "curl", "--", "sh", "-c", loop],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(r.stderr)
    out = r.stdout.strip().splitlines()
    rows = []
    for line in out:
        body, _, code = line.rpartition("|")
        rows.append((code, body.strip()))
    return rows


@given('the traffic spec "{path}" is applied')
def apply_spec(context, path):
    local = os.path.join(context.tmp, os.path.basename(path))
    shutil.copy(path, local)
    context.spec = local
    sh(f"{PY} -m meshctl apply {local}")
    time.sleep(3)  # let the sidecars receive the new configuration


@when('I send {n:d} requests to "{svc}" from the mesh client')
def send(context, n, svc):
    context.rows = mesh_curl(f"{svc}:5678", n)


@when('I send {n:d} slow requests to "{svc}" from the mesh client')
def send_slow(context, n, svc):
    context.rows = mesh_curl(f"{svc}:5678", n, sleep=0.1)


@when('I set the weights "{pairs}" with meshctl and apply')
def set_and_apply(context, pairs):
    sh(f"{PY} -m meshctl set-weights {context.spec} {pairs}")
    sh(f"{PY} -m meshctl apply {context.spec}")
    time.sleep(3)


@when('I try to set the weights "{pairs}" with meshctl')
def try_set(context, pairs):
    local = os.path.join(context.tmp, "traffic.yaml")
    shutil.copy("mesh/traffic.yaml", local)
    context.result = sh(f"{PY} -m meshctl set-weights {local} {pairs}", check=False)


@then('between {lo:d} and {hi:d} percent of responses are "{word}"')
def share(context, lo, hi, word):
    pct = 100 * sum(1 for _, b in context.rows if b == word) / len(context.rows)
    assert lo <= pct <= hi, f"{pct:.1f}% were {word}, expected {lo} to {hi}"


@then('meshctl refuses with "{text}"')
def refuses(context, text):
    assert context.result.returncode != 0 and text in context.result.stdout, context.result.stdout


@when('a pod without a sidecar calls "{target}"')
def legacy_call(context, target):
    context.result = sh(f"kubectl -n legacy exec deploy/legacy-client -- curl -s -m 5 http://{target}/", check=False)


@then("the call fails")
def call_fails(context):
    assert context.result.returncode != 0, f"unexpected success: {context.result.stdout}"


@then('a pod in the mesh can call "{target}"')
def mesh_call(context, target):
    rows = mesh_curl(target, 3)
    assert all(c == "200" for c, _ in rows), rows


@then("fewer than {n:d} responses are errors")
def few_errors(context, n):
    errors = sum(1 for c, _ in context.rows if c != "200")
    assert errors < n, f"{errors} errors out of {len(context.rows)}"


@then("the last {n:d} responses are all successful")
def last_ok(context, n):
    tail = context.rows[-n:]
    assert all(c == "200" for c, _ in tail), tail


@when('I scale "{dep}" to {n:d} replicas')
def scale(context, dep, n):
    sh(f"kubectl -n shop scale deploy/{dep} --replicas={n}")


@then('{n:d} replicas of "{dep}" are ready within {secs:d} seconds')
def ready(context, n, dep, secs):
    deadline = time.time() + secs
    while time.time() < deadline:
        got = sh(f"kubectl -n shop get deploy/{dep} -o jsonpath='{{.status.readyReplicas}}'").stdout.strip("'") or "0"
        if int(got) == n and sh(f"kubectl -n shop get pods -l app=web,version=v1 --no-headers | wc -l").stdout.strip() == str(n):
            return
        time.sleep(2)
    raise AssertionError(f"{dep} not at {n} ready replicas")


@then('{n:d} requests to "{svc}" return no errors')
def load_no_errors(context, n, svc):
    rows = mesh_curl(f"{svc}:5678", n)
    bad = [r for r in rows if r[0] != "200"]
    assert not bad, f"{len(bad)} of {n} failed"
