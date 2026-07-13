"""job-finder CLI dispatch.

  python -m jobfinder [--resume … ]      → discover + score + rank (default)
  python -m jobfinder doctor [--json]    → cold-start setup check
  python -m jobfinder onboard            → first-run guided setup
  python -m jobfinder dashboard          → local tracker UI (feedback loop)
  python -m jobfinder feedback --job …   → record a correction from the CLI
"""

import sys


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] == "doctor":
        from .doctor import main as doctor_main
        return doctor_main(argv[1:])

    if argv and argv[0] == "onboard":
        from .onboard import cmd as onboard_cmd
        return onboard_cmd(argv[1:])

    if argv and argv[0] == "dashboard":
        from .dashboard import serve
        port = 8755
        if "--port" in argv:
            port = int(argv[argv.index("--port") + 1])
        return serve(port)

    if argv and argv[0] == "feedback":
        import argparse
        from . import feedback
        ap = argparse.ArgumentParser(prog="jobfinder feedback")
        ap.add_argument("--job", required=True, help="job_id (from results)")
        ap.add_argument("--action", required=True, choices=list(feedback.ACTIONS))
        ap.add_argument("--note", default="")
        ap.add_argument("--company", default="")
        ap.add_argument("--title", default="")
        ap.add_argument("--url", default="")
        a = ap.parse_args(argv[1:])
        feedback.record(a.job, a.company, a.title, a.url, a.action, a.note)
        label = feedback.ACTIONS[a.action][0]
        print(f"recorded: {label} — {a.company} {a.title}".rstrip())
        return 0

    if argv and argv[0] in ("discover", "prescreen", "enrich", "tracker", "live"):
        from .agent_tools import HANDLERS
        return HANDLERS[argv[0]](argv[1:])

    from .run import main as run_main
    return run_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
