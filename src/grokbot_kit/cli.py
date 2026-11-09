"""Ponto de entrada do executável `grokbot-kit`.

`grokbot-kit emit` é chamado pelos hooks dos agentes e respeita a door 6: o despacho acontece antes de qualquer
import além de `os` e `sys`, então `argparse` e o resto só carregam nos outros comandos.
"""

import sys

# `typing` também fica fora do caminho do `emit`; o mypy reconhece o nome `TYPE_CHECKING` mesmo sem ele.
TYPE_CHECKING = False
if TYPE_CHECKING:
    import argparse


def build_parser() -> "argparse.ArgumentParser":
    import argparse

    from grokbot_kit import __version__
    from grokbot_kit.launch import TOOLS

    parser = argparse.ArgumentParser(
        prog="grokbot-kit",
        description="Delegate tasks to headless coding agents and wake the right Grok Bot routine.",
    )
    parser.add_argument("--version", action="version", version=f"grokbot-kit {__version__}")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="run a headless agent task and notify the target when it ends")
    run.add_argument("--tool", choices=TOOLS)
    run.add_argument("--model")
    run.add_argument("--tier", choices=("trivial", "standard", "complex"))
    run.add_argument("--target", required=True)
    run.add_argument("--label", required=True)
    run.add_argument("--timeout", help="duration such as 30m, 2h or 1d; defaults to timeouts.<tier> in the config")
    run.add_argument(
        "--ask-wait",
        metavar="DURATION",
        help="how long a permission request waits for grokbot-kit reply, such as 10m; 0 only notifies; "
        "defaults to ask.wait in the config (10m)",
    )
    run.add_argument("--cwd")
    run.add_argument("--prompt-file")
    run.add_argument("--plugin", help="run a plugin (see: grokbot-kit plugin list); the prompt comes from it")
    run.add_argument("--input", action="append", default=[], metavar="KEY=VALUE", help="a plugin input; repeatable")
    run.add_argument("extras", nargs="*", metavar="-- ARGS", help="passed verbatim to the agent CLI")

    emit = sub.add_parser("emit", help="called by agent hooks inside a task")
    emit.add_argument("--from", dest="source", choices=TOOLS, required=True)

    reply = sub.add_parser("reply", help="answer a permission request of a running task (allow or deny)")
    reply.add_argument("task_id")
    reply.add_argument("request_id", help="needs_input.request_id of the needs_input event")
    reply.add_argument("decision", choices=("allow", "deny"))
    reply.add_argument("--message", help="why the request is denied; told to the agent (only with deny)")
    reply.add_argument("--by", choices=("user", "bot"), default="user", help="who decided (default: user)")

    redeliver = sub.add_parser("redeliver", help="resend the events of a task that were not delivered")
    redeliver.add_argument("task_id")

    gc = sub.add_parser("gc", help="remove task dirs of tasks that finished long ago")
    gc.add_argument("--older-than", required=True, metavar="DURATION", help="such as 30d, 12h or 90m")
    gc.add_argument("--dry-run", action="store_true", help="only list what would be removed")

    route = sub.add_parser("route", help="manage the route (sinks) of each target bot")
    route_sub = route.add_subparsers(dest="route_command", required=True)
    route_add = route_sub.add_parser("add", help="route a target to its Grok Bot routine")
    route_add.add_argument("target")
    route_add.add_argument("--url-secret", required=True, help="secret holding the routine webhook URL")
    route_add.add_argument("--key-secret", required=True, help="secret holding the routine key (crsr_...)")
    route_add.add_argument("--header", action="append", default=[], help="extra header, 'Name: value'")
    route_sub.add_parser("rm", help="remove the route of a target").add_argument("target")
    route_sub.add_parser("test", help="send a test event to every sink of the route").add_argument("target")

    setup = sub.add_parser("setup", help="set up the agent CLIs")
    setup_sub = setup.add_subparsers(dest="setup_command", required=True)
    setup_cli = setup_sub.add_parser("cli", help="install agent CLIs")
    setup_cli_sub = setup_cli.add_subparsers(dest="cli_command", required=True)
    cli_add = setup_cli_sub.add_parser("add", help="install a CLI with its official installer and record it")
    cli_add.add_argument("tool", choices=TOOLS)
    cli_upgrade = setup_cli_sub.add_parser(
        "upgrade", help="upgrade a CLI with its official installer (and the opencode plugin with it)"
    )
    cli_upgrade.add_argument("tool", choices=TOOLS)
    setup_sub.add_parser("default", help="set the CLI used when a task names none").add_argument("tool", choices=TOOLS)
    tiers = setup_sub.add_parser("tiers", help="set the ordered model ids of a tier (discovered ids only)")
    tiers.add_argument("tool", choices=TOOLS)
    tiers.add_argument("tier", choices=("trivial", "standard", "complex"))
    tiers.add_argument("ids", nargs="+", metavar="ID")
    providers = setup_sub.add_parser(
        "providers", help="opencode: set the providers whose model ids the tiers may use, in order"
    )
    providers.add_argument("tool", choices=TOOLS)
    providers.add_argument("providers", nargs="+", metavar="PROVIDER", help="the text before the first / of an id")
    models = setup_sub.add_parser("models", help="model ids discovered for each CLI")
    models_sub = models.add_subparsers(dest="models_command", required=True)
    refresh = models_sub.add_parser("refresh", help="discover the model ids of a CLI (or of every installed one)")
    refresh.add_argument("tool", nargs="?", choices=TOOLS)
    refresh.add_argument(
        "--add", action="append", default=[], metavar="ID", help="claude/codex: also test and record this model id"
    )
    refresh.add_argument("--json", action="store_true", help="machine-readable output, with the provider of each id")

    login = sub.add_parser("login", help="log a CLI in with its official command")
    login.add_argument("tool", choices=TOOLS)
    login.add_argument("--method", choices=("subscription", "api-key"), default="subscription")
    login.add_argument("--secret", metavar="NAME", help="secret holding the API key (default: <tool>-api-key)")

    doctor = sub.add_parser("doctor", help="check versions, CLIs, logins, routes and secrets")
    doctor.add_argument("--json", action="store_true", help="machine-readable output")

    install = sub.add_parser("install", help="install the opencode plugin (inert outside a task)")
    install.add_argument("target", choices=("opencode",))
    uninstall = sub.add_parser("uninstall", help="remove the opencode plugin")
    uninstall.add_argument("target", choices=("opencode",))

    update = sub.add_parser("update", help="check for a new grokbot-kit release and upgrade to it")
    update_sub = update.add_subparsers(dest="update_command", required=True)
    update_sub.add_parser("check", help="tell whether a new release exists").add_argument(
        "--json", action="store_true", help="machine-readable output"
    )
    update_sub.add_parser("apply", help="upgrade with the tool that installed grokbot-kit and rewrite the plugin")
    update_sub.add_parser("skip", help="do not ask again about this version").add_argument("version")
    update_sub.add_parser("later", help="do not ask again for 24 hours")

    plugin = sub.add_parser("plugin", help="list, inspect, install and remove plugins (ready-made tasks)")
    plugin_sub = plugin.add_subparsers(dest="plugin_command", required=True)
    plugin_sub.add_parser("list", help="builtin and installed plugins").add_argument(
        "--json", action="store_true", help="machine-readable output"
    )
    plugin_show = plugin_sub.add_parser("show", help="manifest, inputs, capabilities and support of each CLI")
    plugin_show.add_argument("plugin", metavar="NAME_OR_ORIGIN", help="installed name, directory or git URL")
    plugin_show.add_argument("--json", action="store_true", help="machine-readable output")
    plugin_add = plugin_sub.add_parser("add", help="install a pinned copy of a plugin from a directory or git URL")
    plugin_add.add_argument("origin", help="directory or git URL")
    plugin_add.add_argument("--ref", help="git branch, tag or commit (default: the default branch)")
    plugin_add.add_argument("--replace", action="store_true", help="install over a plugin with the same name")
    plugin_add.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    plugin_sub.add_parser("rm", help="remove an installed plugin").add_argument("name")

    secret = sub.add_parser("secret", help="store secrets in ~/.secrets/grokbot-kit/ (mode 0600)")
    secret_sub = secret.add_subparsers(dest="secret_command", required=True)
    secret_sub.add_parser("set", help="read a secret from the terminal (no echo) or stdin").add_argument("name")
    return parser


def main(argv: list[str] | None = None) -> int:
    args_list = sys.argv[1:] if argv is None else argv
    if args_list[:1] == ["emit"]:
        from grokbot_kit import emit

        return emit.main(args_list[1:])

    parser = build_parser()
    args = parser.parse_args(args_list)
    if args.command == "run":
        from grokbot_kit.run import run

        return run(args)
    if args.command == "reply":
        from grokbot_kit.reply import reply

        return reply(args.task_id, args.request_id, args.decision, args.message, args.by)
    if args.command == "redeliver":
        from grokbot_kit.redeliver import redeliver

        return redeliver(args.task_id)
    if args.command == "gc":
        from grokbot_kit.gc import gc

        return gc(args.older_than, args.dry_run)
    if args.command == "route":
        from grokbot_kit import route

        if args.route_command == "add":
            return route.add(args.target, args.url_secret, args.key_secret, args.header)
        return route.rm(args.target) if args.route_command == "rm" else route.test(args.target)
    if args.command == "setup":
        from grokbot_kit import setup

        if args.setup_command == "cli":
            return setup.cli_add(args.tool) if args.cli_command == "add" else setup.cli_upgrade(args.tool)
        if args.setup_command == "default":
            return setup.set_default(args.tool)
        if args.setup_command == "tiers":
            return setup.set_tiers(args.tool, args.tier, args.ids)
        if args.setup_command == "providers":
            return setup.set_providers(args.tool, args.providers)
        from grokbot_kit.models import refresh

        return refresh(args.tool, args.add, args.json)
    if args.command == "login":
        from grokbot_kit.login import login

        return login(args.tool, args.method, args.secret)
    if args.command == "doctor":
        from grokbot_kit.doctor import doctor

        return doctor(args.json)
    if args.command in ("install", "uninstall"):
        from grokbot_kit import opencode_plugin

        return opencode_plugin.install() if args.command == "install" else opencode_plugin.uninstall()
    if args.command == "update":
        from grokbot_kit import update

        if args.update_command == "check":
            return update.check(args.json)
        if args.update_command == "apply":
            return update.apply()
        return update.skip(args.version) if args.update_command == "skip" else update.later()
    if args.command == "plugin":
        from grokbot_kit import plugin

        if args.plugin_command == "list":
            return plugin.list_cmd(args.json)
        if args.plugin_command == "show":
            return plugin.show(args.plugin, args.json)
        if args.plugin_command == "add":
            return plugin.add(args.origin, args.ref, args.replace, args.yes)
        return plugin.rm(args.name)
    if args.command == "secret":
        from grokbot_kit.secret import set_secret

        return set_secret(args.name)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
