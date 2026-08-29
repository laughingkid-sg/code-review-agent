from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .env import load_env_file
from .providers import ChatMessage, OpenAICompatibleProvider, ProviderError
from .review import run_aggregate, run_business_rules, run_code_rules
from .rules import load_rules


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code-review-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a deterministic dry-run review.")
    run_parser.add_argument("--mode", choices=("code-rules", "business-rules", "aggregate"), required=True)
    run_parser.add_argument("--config", default=".code-review.yml")
    run_parser.add_argument("--repository", default=".")
    run_parser.add_argument("--knowledgebase", default="../code-review-knowledgebase")
    run_parser.add_argument("--output", required=True)
    run_parser.add_argument("--default-contributor", default="codex")
    run_parser.add_argument("--changed-file", action="append", default=[])

    smoke_parser = subparsers.add_parser("smoke-provider", help="Run a small OpenAI-compatible provider smoke test.")
    smoke_parser.add_argument("--env-file", default=".env")
    smoke_parser.add_argument("--prompt", default="Reply with exactly: OK")
    smoke_parser.add_argument("--max-tokens", type=int, default=16)

    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args)
    if args.command == "smoke-provider":
        return _smoke_provider(args)
    return 1


def _run(args: argparse.Namespace) -> int:
    repository_path = Path(args.repository).resolve()
    config_path = _resolve_path(repository_path, args.config)
    knowledgebase_path = Path(args.knowledgebase).resolve()
    output_path = _resolve_path(repository_path, args.output)
    changed_files = tuple(_resolve_path(repository_path, path) for path in args.changed_file)
    config = load_config(config_path, repository_path)

    if args.mode == "code-rules":
        rules = load_rules(knowledgebase_path, config.knowledge_layers, config.disabled_rules)
        run_code_rules(
            config=config,
            rules=rules,
            repository_path=repository_path,
            changed_files=changed_files,
            output_path=output_path,
            default_contributor=args.default_contributor,
        )
    elif args.mode == "business-rules":
        run_business_rules(config=config, changed_files=changed_files, output_path=output_path)
    elif args.mode == "aggregate":
        run_aggregate(output_path=output_path)
    return 0


def _resolve_path(repository_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repository_path / path


def _smoke_provider(args: argparse.Namespace) -> int:
    load_env_file(Path(args.env_file).resolve())
    try:
        provider = OpenAICompatibleProvider.from_env()
        result = provider.chat(
            [
                ChatMessage(role="system", content="You are a concise connectivity test."),
                ChatMessage(role="user", content=args.prompt),
            ],
            max_tokens=args.max_tokens,
            temperature=0,
        )
    except ProviderError as exc:
        print(f"Provider smoke test failed: {exc}")
        return 1

    print("Provider smoke test passed.")
    print(f"Model: {result.model}")
    if result.usage:
        print(f"Usage: {result.usage}")
    print(f"Response: {result.content}")
    return 0
