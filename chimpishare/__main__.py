import argparse
import getpass
import json
import sys
from pathlib import Path

from . import __version__
from .bridge import diagnose
from .errors import ShareError
from .settings import Translator, load_settings
from .transfer import Receiver, send_file


def main(argv=None):
    t = Translator(load_settings()["language"])
    parser = argparse.ArgumentParser(description=t("cli_description"))
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("gui", help="ChimpiShare")
    commands.add_parser("doctor", help=t("diagnostics"))
    for command in ("self-test", "gui-smoke"):
        check = commands.add_parser(command, help=t("build_check"))
        check.add_argument("--output", required=True)
    receive = commands.add_parser("receive", help=t("receive"))
    receive.add_argument("--folder", required=True, help=t("cli_folder"))
    receive.add_argument("--host", required=True, help=t("cli_host"))
    receive.add_argument("--port", type=int, default=48765, help=t("cli_port"))
    receive.add_argument("--max-mib", type=int, default=2048, help=t("cli_max_mib"))
    send = commands.add_parser("send", help=t("send"))
    send.add_argument("file", help=t("cli_file"))
    send.add_argument("--invite-file", help=t("cli_invite_file"))
    args = parser.parse_args(argv)
    try:
        if args.command in {None, "gui"}:
            from .gui import App
            App().run()
        elif args.command == "doctor":
            print(json.dumps(diagnose(), indent=2, ensure_ascii=False))
        elif args.command in {"self-test", "gui-smoke"}:
            from .verification import verify_gui, verify_transfer
            report = verify_gui() if args.command == "gui-smoke" else verify_transfer()
            Path(args.output).write_text(json.dumps(report, indent=2), "utf-8")
        elif args.command == "send":
            invitation = (Path(args.invite_file).read_text("utf-8").strip() if args.invite_file
                          else getpass.getpass(t("cli_invite_prompt")))
            result = send_file(invitation, args.file)
            print(t("sent_ok", name=result["name"]))
        elif args.command == "receive":
            if not 1 <= args.port <= 65535 or not 1 <= args.max_mib <= 1024 * 1024:
                raise ShareError("invalid_request")

            def approve(offer):
                return input(t("cli_approval", name=offer.name, size=offer.size, peer=offer.peer)).strip().lower() in {"s", "sim", "y", "yes"}

            def notify(kind, **values):
                print(t("received_ok", path=values["path"]))

            receiver = Receiver(args.folder, approve, notify, host=args.host, port=args.port,
                                max_bytes=args.max_mib * 1024 * 1024)
            try:
                print(t("cli_invitation", invitation=receiver.invitation(args.host)), flush=True)
                receiver.start()
                while receiver.thread.is_alive():
                    receiver.thread.join(timeout=0.5)
            finally:
                receiver.close()
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        if args.command in {"self-test", "gui-smoke"}:
            import traceback
            traceback.print_exc()
        text = t(exc.code, **exc.values) if isinstance(exc, ShareError) else t("system_error", error=str(exc))
        print(text, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
