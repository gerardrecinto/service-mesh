import copy
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import HTTPServer

import pytest
import yaml

from meshctl import spec as S
from meshctl import ui

GOOD = S.load("mesh/traffic.yaml")


def mutate(**kw):
    s = copy.deepcopy(GOOD)
    s.update(kw)
    return s


def test_shipped_spec_is_valid():
    assert S.validate(GOOD) == []


@pytest.mark.parametrize("bad,needle", [
    (mutate(subsets={"v1": 60, "v2": 60}), "add up to 120"),
    (mutate(subsets={"v1": -5, "v2": 105}), "0 to 100"),
    (mutate(subsets={}), "empty"),
    (mutate(port=70000), "port"),
    (mutate(retries={"attempts": 9, "perTryTimeout": "2s", "retryOn": "5xx"}), "retry storm"),
    (mutate(retries={"attempts": 2, "perTryTimeout": "fast", "retryOn": "5xx"}), "perTryTimeout"),
    (mutate(outlier={"consecutive5xx": 0, "interval": "2s", "baseEjection": "30s", "maxEjectionPercent": 50}), "consecutive5xx"),
    (mutate(mtls="MAYBE"), "mtls"),
    (mutate(service="Bad_Name"), "DNS labels"),
])
def test_invalid_specs_are_rejected(bad, needle):
    assert any(needle in e for e in S.validate(bad))


def test_render_builds_weighted_route_outlier_and_strict_mtls():
    dr, vs, pa = S.render(GOOD)
    assert [s["name"] for s in dr["spec"]["subsets"]] == ["v1", "v2"]
    assert dr["spec"]["trafficPolicy"]["tls"]["mode"] == "ISTIO_MUTUAL"
    assert dr["spec"]["trafficPolicy"]["outlierDetection"]["consecutive5xxErrors"] == 3
    weights = {r["destination"]["subset"]: r["weight"] for r in vs["spec"]["http"][0]["route"]}
    assert weights == {"v1": 90, "v2": 10}
    assert vs["spec"]["http"][0]["retries"]["attempts"] == 2
    assert pa["spec"]["mtls"]["mode"] == "STRICT"


def test_zero_weight_subset_is_left_out_of_the_route():
    vs = S.render(mutate(subsets={"v1": 100, "v2": 0}))[1]
    assert [r["destination"]["subset"] for r in vs["spec"]["http"][0]["route"]] == ["v1"]


def test_ui_applies_valid_weights_and_rejects_bad_ones(tmp_path):
    path = tmp_path / "traffic.yaml"
    path.write_text(yaml.safe_dump(GOOD))
    srv = HTTPServer(("127.0.0.1", 0), ui.handler(str(path), kubectl=False))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}"
    assert b"web traffic" in urllib.request.urlopen(url).read()

    def post(v1, v2):
        data = urllib.parse.urlencode({"v1": v1, "v2": v2}).encode()
        return urllib.request.urlopen(urllib.request.Request(url, data=data))

    assert post(50, 50).status == 200
    assert S.load(str(path))["subsets"] == {"v1": 50, "v2": 50}
    with pytest.raises(urllib.error.HTTPError) as e:
        post(80, 80)
    assert e.value.code == 422 and b"add up to 160" in e.value.read()
    assert S.load(str(path))["subsets"] == {"v1": 50, "v2": 50}
    srv.shutdown()
