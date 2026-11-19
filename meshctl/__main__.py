import argparse
import subprocess
import sys

from . import spec as S


def main(argv=None):
    p = argparse.ArgumentParser(prog="meshctl")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, helptext in (("validate", "check a traffic spec"), ("render", "print the Istio YAML"),
                           ("apply", "validate, render and kubectl apply")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("file")
    s = sub.add_parser("set-weights", help="change subset weights in a spec file, then validate")
    s.add_argument("file")
    s.add_argument("weights", nargs="+", help="subset=weight pairs, for example v1=50 v2=50")
    s = sub.add_parser("ui", help="serve the small web page for editing weights")
    s.add_argument("file")
    s.add_argument("--port", type=int, default=8088)
    a = p.parse_args(argv)

    if a.cmd == "ui":
        from .ui import serve
        serve(a.file, a.port)
        return 0
    spec = S.load(a.file)
    if a.cmd == "set-weights":
        for pair in a.weights:
            name, _, weight = pair.partition("=")
            spec["subsets"][name] = int(weight)
        errors = S.validate(spec)
        if errors:
            print("\n".join(f"ERROR {e}" for e in errors))
            return 1
        import yaml
        open(a.file, "w").write(yaml.safe_dump(spec, sort_keys=False))
        print("updated", a.file)
        return 0
    errors = S.validate(spec)
    if errors:
        print("\n".join(f"ERROR {e}" for e in errors))
        return 1
    if a.cmd == "validate":
        print("valid")
    elif a.cmd == "render":
        print(S.to_yaml(S.render(spec)))
    else:
        subprocess.run(["kubectl", "apply", "-f", "-"], input=S.to_yaml(S.render(spec)), text=True, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
