"""A one-page web UI for the traffic weights. Standard library only; binds to localhost."""
import html
import json
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

from . import spec as S

PAGE = """<!doctype html><meta charset=utf-8><title>meshctl</title>
<style>body{{font:16px system-ui;max-width:34rem;margin:2rem auto;padding:0 1rem}}label{{display:block;margin:.6rem 0}}
input[type=number]{{width:5rem}}.err{{color:#b00020}}.ok{{color:#0a6b2d}}</style>
<h1>{service} traffic</h1><form method=post>
{rows}<button>Validate and apply</button></form><p class="{cls}" role=status>{msg}</p>"""


def render_page(spec, msg="", ok=True):
    rows = "".join(f'<label>{html.escape(n)} <input type=number name="{html.escape(n)}" min=0 max=100 value={w}> %</label>'
                   for n, w in spec["subsets"].items())
    return PAGE.format(service=html.escape(spec["service"]), rows=rows, msg=html.escape(msg), cls="ok" if ok else "err")


def apply_weights(path, form, kubectl=True):
    """Return (ok, message). Writes the file only when the new weights validate."""
    spec = S.load(path)
    try:
        for name in spec["subsets"]:
            spec["subsets"][name] = int(form.get(name, [spec["subsets"][name]])[0])
    except ValueError:
        return False, "weights must be whole numbers"
    errors = S.validate(spec)
    if errors:
        return False, "; ".join(errors)
    import yaml
    open(path, "w").write(yaml.safe_dump(spec, sort_keys=False))
    if kubectl:
        subprocess.run(["kubectl", "apply", "-f", "-"], input=S.to_yaml(S.render(spec)), text=True, check=True,
                       capture_output=True)
    return True, "applied " + json.dumps(spec["subsets"])


def handler(path, kubectl=True):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, code=200):
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self._send(render_page(S.load(path)))

        def do_POST(self):
            form = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode())
            ok, msg = apply_weights(path, form, kubectl)
            self._send(render_page(S.load(path), msg, ok), 200 if ok else 422)
    return H


def serve(path, port):
    print(f"meshctl ui on http://127.0.0.1:{port}")
    HTTPServer(("127.0.0.1", port), handler(path)).serve_forever()
