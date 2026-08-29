from __future__ import annotations

import argparse
from pathlib import Path

from .audit import AuditRecorder
from .config import load_config
from .env import load_env_file
from .github import GitHubError
from .providers import ChatMessage, OpenAICompatibleProvider, ProviderError
from .rules import load_rules
from .skills import aggregation, business_rules, code_rules, github_comments


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
    run_parser.add_argument("--provider", choices=("mock", "llm", "qwen"), default="mock")
    run_parser.add_argument("--env-file", default=".env")
    run_parser.add_argument("--audit-dir", default="output")
    run_parser.add_argument("--comment-mode", choices=("dry_run", "pr_comment"), default="dry_run")
    run_parser.add_argument("--summary-cache-ttl-days", type=int, default=3)
    run_parser.add_argument("--aggregate-input", action="append", default=[])
    run_parser.add_argument("--artifact-link", action="append", default=[])

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
    aggregate_inputs = tuple(_resolve_path(repository_path, path) for path in args.aggregate_input)
    config = load_config(config_path, repository_path)
    try:
        provider = _provider_from_args(args, repository_path)
    except ProviderError as exc:
        print(f"Provider configuration failed: {exc}")
        return 1
    audit_recorder = AuditRecorder(_resolve_path(repository_path, args.audit_dir)) if provider else None

    if args.mode == "code-rules":
        rules = load_rules(knowledgebase_path, config.knowledge_layers, config.disabled_rules)
        code_rules.run(
            config=config,
            rules=rules,
            repository_path=repository_path,
            changed_files=changed_files,
            output_path=output_path,
            default_contributor=args.default_contributor,
            provider=provider,
            audit_recorder=audit_recorder,
        )
    elif args.mode == "business-rules":
        business_rules.run(
            config=config,
            repository_path=repository_path,
            changed_files=changed_files,
            output_path=output_path,
            provider=provider,
            audit_recorder=audit_recorder,
            summary_cache_ttl_days=args.summary_cache_ttl_days,
        )
    elif args.mode == "aggregate":
        aggregation.run(output_path=output_path, input_paths=aggregate_inputs)
    try:
        github_comments.publish(
            mode=args.mode,
            output_path=output_path,
            repository_path=repository_path,
            comment_mode=args.comment_mode,
            artifact_links=tuple(args.artifact_link),
        )
    except GitHubError as exc:
        print(f"GitHub comment publishing failed: {exc}")
        return 1
    return 0


def _resolve_path(repository_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (repository_path / path).resolve()


def _provider_from_args(args: argparse.Namespace, repository_path: Path) -> OpenAICompatibleProvider | None:
    if args.provider == "mock":
        return None
    load_env_file(_resolve_path(repository_path, args.env_file))
    return OpenAICompatibleProvider.from_env()


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
