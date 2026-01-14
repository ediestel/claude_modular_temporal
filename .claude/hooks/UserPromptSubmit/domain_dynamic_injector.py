#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

import requests
from requests import RequestException, Timeout


# Paths
STATE_FILE = pathlib.Path(os.path.expanduser("~/.claude/claudine_state.json"))
CACHE_FILE = pathlib.Path(os.path.expanduser("~/.claude/claudine_domain_cache.json"))
SESSION_FILE = pathlib.Path(os.path.expanduser("~/.claude/claudine_session.json"))
LOG_FILE_DEFAULT = pathlib.Path(os.path.expanduser("~/.claude/claudine_hook.log"))

# Version for cache invalidation (bump to force regeneration)
CACHE_VERSION = "1"

# Patterns
DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")
# Supports multi-domain: /domain:math,python
DOMAIN_OVERRIDE_RE = re.compile(r"(?i)(?:^|\s)/domain:([a-z0-9][a-z0-9_,\-]{1,63})(?:\s|$)")


# PII-ish patterns (optional; default OFF). This is intentionally lightweight.
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d[\d\-\s().]{7,}\d)\b")
API_KEYISH_RE = re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*\S+")


@dataclass(frozen=True)
class Settings:
    fail_open: bool = True

    # Hook output behavior
    suppress_output: bool = True  # hide injected text from transcript output
    show_notice: bool = True      # show a small user-visible notice when applied

    # External calls
    anthropic_timeout_s: int = 15
    grok_timeout_s: int = 60
    api_retry_attempts: int = 2
    api_retry_delay_s: float = 1.0

    # Models (configurable via env)
    anthropic_model: str = "claude-3-haiku-20240307"
    grok_model: str = "grok-4.1-fast-reasoning"

    # Caching (no TTL - invalidate via meta_hash mismatch or manual clear)
    cache_enabled: bool = True

    # Template validation
    template_min_chars: int = 200
    template_max_chars: int = 16000

    # PII redaction
    pii_redaction_enabled: bool = False  # default OFF

    # Optional dotenv
    load_dotenv: bool = False

    # Logging
    log_file: Optional[pathlib.Path] = None
    debug_log: bool = False  # if true, logs more (still avoids full prompt/template unless you change it)


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None:
        return default
    try:
        return int(v.strip())
    except ValueError:
        return default


def _load_settings() -> Settings:
    return Settings(
        fail_open=True,

        suppress_output=_env_bool("CLAUDINE_SUPPRESS_OUTPUT", True),
        show_notice=_env_bool("CLAUDINE_SHOW_NOTICE", True),

        anthropic_timeout_s=_env_int("CLAUDINE_ANTHROPIC_TIMEOUT_S", 15),
        grok_timeout_s=_env_int("CLAUDINE_GROK_TIMEOUT_S", 60),
        api_retry_attempts=_env_int("CLAUDINE_API_RETRY_ATTEMPTS", 2),
        api_retry_delay_s=float(_env_int("CLAUDINE_API_RETRY_DELAY_MS", 1000)) / 1000.0,

        anthropic_model=os.getenv("CLAUDINE_ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
        grok_model=os.getenv("CLAUDINE_GROK_MODEL", "grok-4.1-fast-reasoning"),

        cache_enabled=_env_bool("CLAUDINE_CACHE_ENABLED", True),

        template_min_chars=_env_int("CLAUDINE_TEMPLATE_MIN_CHARS", 200),
        template_max_chars=_env_int("CLAUDINE_TEMPLATE_MAX_CHARS", 16000),

        pii_redaction_enabled=_env_bool("CLAUDINE_PII_REDACTION", False),

        load_dotenv=_env_bool("CLAUDINE_LOAD_DOTENV", False),

        log_file=pathlib.Path(os.path.expanduser(os.getenv("CLAUDINE_LOG_FILE", ""))).resolve()
        if os.getenv("CLAUDINE_LOG_FILE")
        else None,
        debug_log=_env_bool("CLAUDINE_DEBUG_LOG", False),
    )


def _maybe_load_dotenv(settings: Settings) -> None:
    if not settings.load_dotenv:
        return
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return

    project_dir = os.getenv("CLAUDE_PROJECT_DIR")
    if project_dir:
        load_dotenv(os.path.join(project_dir, ".env"), override=False)
    else:
        load_dotenv(override=False)


def _chmod_600_best_effort(path: pathlib.Path) -> None:
    try:
        path.chmod(0o600)
    except Exception:
        pass


def _atomic_write_json(path: pathlib.Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    _chmod_600_best_effort(tmp)
    tmp.replace(path)
    _chmod_600_best_effort(path)


def _read_json_file(path: pathlib.Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except Exception:
        # Corrupted; best-effort quarantine
        try:
            ts = int(time.time())
            path.rename(path.with_suffix(path.suffix + f".corrupt.{ts}"))
        except Exception:
            pass
        return None


def _log(settings: Settings, msg: str) -> None:
    log_path = settings.log_file or (LOG_FILE_DEFAULT if _env_bool("CLAUDINE_LOG_DEFAULT", False) else None)
    if not log_path:
        return
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line)
        _chmod_600_best_effort(log_path)
    except Exception:
        pass


def _emit_additional_context(settings: Settings, additional_context: str, *, system_message: Optional[str] = None) -> None:
    output: dict[str, Any] = {
        "suppressOutput": settings.suppress_output,
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional_context,
        },
    }
    if system_message:
        output["systemMessage"] = system_message
    print(json.dumps(output, ensure_ascii=False))


def _block_prompt(reason: str) -> None:
    # For UserPromptSubmit: blocks prompt processing and erases submitted prompt from context.
    print(json.dumps({"decision": "block", "reason": reason, "suppressOutput": True}, ensure_ascii=False))


def _is_enabled() -> bool:
    state = _read_json_file(STATE_FILE) or {"enabled": False}
    try:
        return bool(state.get("enabled", False))
    except Exception:
        return False


def _set_enabled(enabled: bool) -> None:
    _atomic_write_json(STATE_FILE, {"enabled": enabled})


def _pii_redact(text: str) -> Tuple[str, bool]:
    original = text
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = API_KEYISH_RE.sub("[REDACTED_SECRET]", text)
    return text, (text != original)


def _extract_domain_override(prompt: str) -> Tuple[Optional[str], str]:
    """Extract domain override(s) from prompt. Returns (comma-sep domains or None, prompt without override)."""
    m = DOMAIN_OVERRIDE_RE.search(prompt)
    if not m:
        return None, prompt
    override = (m.group(1) or "").strip().lower()
    prompt_wo = (prompt[: m.start()] + " " + prompt[m.end() :]).strip()
    return override, prompt_wo


def _parse_multi_domain(override: str) -> List[str]:
    """Parse comma-separated domains into a normalized list."""
    if not override:
        return []
    parts = [p.strip() for p in override.split(",")]
    normalized = []
    for p in parts:
        d = _normalize_domain(p)
        if d and d not in normalized:
            normalized.append(d)
    return normalized


def _normalize_domain(domain: str) -> Optional[str]:
    d = (domain or "").strip().lower()
    if not d:
        return None
    # light synonym mapping (no whitelist)
    synonyms = {
        "js": "javascript",
        "ts": "typescript",
        "py": "python",
        "ml": "machine-learning",
        "ai": "machine-learning",
    }
    d = synonyms.get(d, d)
    if not DOMAIN_RE.match(d):
        return None
    return d


def _cache_key(meta_prompt: str, grok_model: str) -> str:
    """Generate cache key from meta_prompt, model, and version."""
    h = hashlib.sha256()
    h.update(CACHE_VERSION.encode("utf-8"))
    h.update(b"\n")
    h.update(grok_model.encode("utf-8"))
    h.update(b"\n")
    h.update(meta_prompt.encode("utf-8"))
    return h.hexdigest()


def _load_cache() -> dict[str, Any]:
    cache = _read_json_file(CACHE_FILE)
    return cache if isinstance(cache, dict) else {}


def _save_cache(cache: dict[str, Any]) -> None:
    _atomic_write_json(CACHE_FILE, cache)


def _cache_get(settings: Settings, domain: str, meta_hash: str) -> Optional[str]:
    """Get cached template. No TTL - invalidate only on meta_hash mismatch or manual clear."""
    if not settings.cache_enabled:
        return None
    cache = _load_cache()
    entry = cache.get(domain)
    if not isinstance(entry, dict):
        return None
    if entry.get("meta_hash") != meta_hash:
        return None
    template = entry.get("template")
    if not isinstance(template, str):
        return None
    return template


def _cache_put(domain: str, meta_hash: str, template: str, *, grok_model: str) -> None:
    cache = _load_cache()
    cache[domain] = {
        "template": template,
        "created_at": int(time.time()),
        "meta_hash": meta_hash,
        "model": grok_model,
    }
    _save_cache(cache)


def _cache_clear(domain: Optional[str] = None) -> None:
    if domain:
        cache = _load_cache()
        if domain in cache:
            del cache[domain]
            _save_cache(cache)
        return
    # clear all
    _save_cache({})


def _cache_list() -> dict[str, Any]:
    """Return the cache dict for inspection."""
    return _load_cache()


# --- Session template storage ---

def _session_save(domains: List[str], templates: dict[str, str], meta_hashes: dict[str, str]) -> None:
    """Save current domain template(s) as session template."""
    data = {
        "domains": domains,
        "templates": templates,
        "meta_hashes": meta_hashes,
        "saved_at": int(time.time()),
    }
    _atomic_write_json(SESSION_FILE, data)


def _session_load() -> Optional[dict[str, Any]]:
    """Load session template if present."""
    return _read_json_file(SESSION_FILE)


def _session_clear() -> None:
    """Clear session template."""
    try:
        SESSION_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _validate_template(settings: Settings, template: str) -> bool:
    t = (template or "").strip()
    if len(t) < settings.template_min_chars:
        return False
    if len(t) > settings.template_max_chars:
        return False
    # Basic “quality” heuristic: must have multiple lines
    if t.count("\n") < 3:
        return False
    return True


def _anthropic_detect_domain(settings: Settings, prompt_for_detection: str) -> Optional[str]:
    """Call Anthropic to detect domain. Includes retry logic for transient errors."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        return None

    payload = {
        "model": settings.anthropic_model,
        "max_tokens": 10,
        "messages": [
            {
                "role": "user",
                "content": f"Extract primary domain as one lowercase word or 'general': {prompt_for_detection}",
            }
        ],
    }

    last_exc: Optional[Exception] = None
    for attempt in range(settings.api_retry_attempts):
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": anthropic_key, "anthropic-version": "2023-06-01"},
                json=payload,
                timeout=settings.anthropic_timeout_s,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("content")
            if not isinstance(content, list) or not content:
                return None
            text = content[0].get("text")
            if not isinstance(text, str):
                return None
            return text.strip().lower()
        except (Timeout, RequestException) as e:
            last_exc = e
            if attempt < settings.api_retry_attempts - 1:
                time.sleep(settings.api_retry_delay_s)
            continue
        except (ValueError, KeyError):
            return None

    _log(settings, f"anthropic_detect_domain failed after {settings.api_retry_attempts} attempts: {last_exc}")
    return None


def _grok_generate_template(settings: Settings, domain: str, meta_prompt: str) -> Optional[str]:
    """Call Grok to generate template. Includes retry logic for transient errors."""
    grok_key = os.getenv("GROK_API_KEY")
    if not grok_key:
        return None

    last_exc: Optional[Exception] = None
    for attempt in range(settings.api_retry_attempts):
        try:
            resp = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {grok_key}"},
                json={
                    "model": settings.grok_model,
                    "messages": [{"role": "user", "content": meta_prompt}],
                    "temperature": 0.7,
                    "max_tokens": 2000,
                },
                timeout=settings.grok_timeout_s,
            )
            if resp.status_code != 200:
                # Retry on 5xx, not on 4xx
                if 500 <= resp.status_code < 600 and attempt < settings.api_retry_attempts - 1:
                    time.sleep(settings.api_retry_delay_s)
                    continue
                return None
            data = resp.json()
            choices = data.get("choices")
            if not isinstance(choices, list) or not choices:
                return None
            msg = choices[0].get("message")
            if not isinstance(msg, dict):
                return None
            content = msg.get("content")
            if not isinstance(content, str):
                return None
            return content.strip()
        except (Timeout, RequestException) as e:
            last_exc = e
            if attempt < settings.api_retry_attempts - 1:
                time.sleep(settings.api_retry_delay_s)
            continue
        except (ValueError, KeyError):
            return None

    _log(settings, f"grok_generate_template failed after {settings.api_retry_attempts} attempts: {last_exc}")
    return None


def _handle_use_session_template(remainder: str) -> bool:
    """Handle /use_session_template [optional additional prompt].
    
    Re-injects the saved session template(s) into context. If remainder provided,
    emits that as additionalContext along with the template.
    """
    settings = _load_settings()
    _maybe_load_dotenv(settings)
    
    session = _session_load()
    if not session:
        _block_prompt("No session template saved. Use a domain command first (e.g., /domain:python).")
        return True
    
    domains = session.get("domains")
    templates = session.get("templates")
    
    if not isinstance(domains, list) or not isinstance(templates, dict) or not domains:
        _block_prompt("Session template is corrupted or empty. Use a domain command to create one.")
        return True
    
    # Build combined template
    layer_parts = []
    for d in domains:
        tmpl = templates.get(d)
        if tmpl:
            layer_parts.append(f"=== CLAUDINE {d.upper()} DOMAIN LAYER (session) ===\n{tmpl}\n=== END LAYER ===")
    
    if not layer_parts:
        _block_prompt("Session template is empty. Use a domain command to create one.")
        return True
    
    combined = "\n\n".join(layer_parts)
    domain_str = ", ".join(domains)
    notice = f"Domain layer applied: {domain_str} (session template). Use '/domain:X' to change."
    
    # If remainder provided, include it too
    if remainder:
        combined = combined + "\n\n" + remainder
    
    _emit_additional_context(settings, combined, system_message=notice if settings.show_notice else None)
    _log(settings, f"applied session template domains={domain_str}")
    return True


def _handle_activator_command(prompt: str) -> bool:
    """Handle /custom:domain-activator commands. Also handles /use_session_template."""

    # Handle /use_session_template [optional prompt]
    if prompt.startswith("/use_session_template"):
        remainder = prompt[len("/use_session_template"):].strip()
        return _handle_use_session_template(remainder)

    if not prompt.startswith("/custom:domain-activator"):
        return False

    parts = prompt.split()
    if len(parts) < 2:
        _block_prompt("Usage: /custom:domain-activator [enable|disable|status|refresh|clear-cache|list-cache|clear-session] [domain?]")
        return True

    action = parts[1].lower()

    if action == "enable":
        _set_enabled(True)
        _block_prompt("Claudine domain layer ENABLED.")
        return True

    if action == "disable":
        _set_enabled(False)
        _block_prompt("Claudine domain layer DISABLED.")
        return True

    if action == "status":
        session = _session_load()
        session_info = ""
        if session and isinstance(session.get("domains"), list):
            session_info = f"\nSession template: {', '.join(session['domains'])}"
        _block_prompt(f"Claudine domain layer: {'ENABLED' if _is_enabled() else 'DISABLED'}{session_info}")
        return True

    if action == "refresh":
        # refresh requires enabled state? not strictly; we just clear cache entry.
        domain = _normalize_domain(parts[2]) if len(parts) >= 3 else None
        if not domain:
            _block_prompt("Usage: /custom:domain-activator refresh <domain>")
            return True
        _cache_clear(domain)
        _block_prompt(f"Cache cleared for domain '{domain}'. It will regenerate next prompt.")
        return True

    if action in {"clear-cache", "clearcache"}:
        _cache_clear(None)
        _block_prompt("Domain template cache cleared.")
        return True

    if action in {"list-cache", "listcache"}:
        cache = _cache_list()
        if not cache:
            _block_prompt("Cache is empty.")
            return True
        lines = ["Cached domains:"]
        for domain, entry in sorted(cache.items()):
            if isinstance(entry, dict):
                created = entry.get("created_at")
                model = entry.get("model", "?")
                ts_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(created)) if isinstance(created, int) else "?"
                lines.append(f"  • {domain}: model={model}, created={ts_str}")
            else:
                lines.append(f"  • {domain}: (invalid entry)")
        _block_prompt("\n".join(lines))
        return True

    if action in {"clear-session", "clearsession"}:
        _session_clear()
        _block_prompt("Session template cleared.")
        return True

    _block_prompt("Unknown action. Usage: /custom:domain-activator [enable|disable|status|refresh|clear-cache|list-cache|clear-session]")
    return True


def main() -> None:
    settings = _load_settings()
    _maybe_load_dotenv(settings)

    # Parse stdin (fail-open)
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        _log(settings, "invalid stdin JSON; exiting (fail-open)")
        return

    prompt = input_data.get("prompt")
    if not isinstance(prompt, str):
        _log(settings, "missing/invalid prompt; exiting (fail-open)")
        return

    prompt = prompt.strip()
    if not prompt:
        return

    # Control commands should not be forwarded to Claude
    if _handle_activator_command(prompt):
        return

    # If not enabled, do nothing
    if not _is_enabled():
        return

    override_raw, prompt_wo_override = _extract_domain_override(prompt)
    
    # Parse multi-domain if explicit override
    if override_raw:
        domains = _parse_multi_domain(override_raw)
        is_explicit = True
    else:
        domains = []
        is_explicit = False

    # If no explicit override, detect via Anthropic
    if not domains:
        # Prepare prompt text for external domain detection
        prompt_for_detection = prompt_wo_override
        if settings.pii_redaction_enabled:
            prompt_for_detection, redacted = _pii_redact(prompt_for_detection)
            if redacted:
                _log(settings, "PII redaction applied to detection payload")

        domain_raw = _anthropic_detect_domain(settings, prompt_for_detection)
        domain = _normalize_domain(domain_raw or "")
        if domain and domain != "general":
            domains = [domain]

    if not domains:
        return

    # Process each domain: check cache, generate if miss
    templates: dict[str, str] = {}
    meta_hashes: dict[str, str] = {}
    cache_status: dict[str, str] = {}  # domain -> "hit" | "miss"

    for domain in domains:
        meta_prompt = (
            f"Create a comprehensive system-level template for the {domain} domain.\n"
            "Include all best practices, constraints, terminology, patterns, and priorities.\n"
            "Be direct, detailed, exhaustive. Output ONLY the template."
        )
        meta_hash = _cache_key(meta_prompt, settings.grok_model)
        meta_hashes[domain] = meta_hash

        # Cache hit?
        cached = _cache_get(settings, domain, meta_hash)
        if isinstance(cached, str) and _validate_template(settings, cached):
            templates[domain] = cached
            cache_status[domain] = "hit"
            _log(settings, f"cache hit domain={domain}")
            continue

        # Cache miss -> generate
        template = _grok_generate_template(settings, domain, meta_prompt)
        if not template:
            _log(settings, f"grok generation failed domain={domain}; skipping (fail-open)")
            continue

        if not _validate_template(settings, template):
            _log(settings, f"template validation failed domain={domain}; skipping (fail-open)")
            continue

        # Store in cache
        if settings.cache_enabled:
            _cache_put(domain, meta_hash, template, grok_model=settings.grok_model)

        templates[domain] = template
        cache_status[domain] = "miss"
        _log(settings, f"cache miss domain={domain}")

    if not templates:
        # All failed; fail-open
        _log(settings, "no templates generated; exiting (fail-open)")
        return

    # Build combined additional context
    layer_parts = []
    if is_explicit:
        layer_parts.append(f"NOTE: User specified domain override '{', '.join(domains)}'. Ignore any /domain:... token in the prompt.")

    for domain in domains:
        tmpl = templates.get(domain)
        if tmpl:
            status = cache_status.get(domain, "?")
            layer_parts.append(f"=== CLAUDINE {domain.upper()} DOMAIN LAYER ({status}) ===\n{tmpl}\n=== END LAYER ===")

    additional = "\n\n".join(layer_parts)

    # Build notice
    domain_str = ", ".join(templates.keys())
    hit_count = sum(1 for s in cache_status.values() if s == "hit")
    miss_count = sum(1 for s in cache_status.values() if s == "miss")
    status_summary = []
    if hit_count:
        status_summary.append(f"{hit_count} cached")
    if miss_count:
        status_summary.append(f"{miss_count} generated")
    status_text = ", ".join(status_summary) if status_summary else ""
    notice = f"Domain: {domain_str} ({status_text}). Use '/domain:X' to change." if settings.show_notice else None

    # Save as session template
    _session_save(list(templates.keys()), templates, meta_hashes)

    _emit_additional_context(settings, additional, system_message=notice)
    _log(settings, f"applied domains={domain_str}")


if __name__ == "__main__":
    main()