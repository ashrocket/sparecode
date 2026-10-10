"""Small HTTP adapter and conservative, per-run request accounting."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import ipaddress
import json
import os
import urllib.error
import urllib.parse
import urllib.request


OPENROUTER = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "qwen/qwen3-coder-next"


class HarnessError(Exception):
    pass


def money(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise HarnessError("Invalid price or budget") from None
    if not result.is_finite() or result < 0:
        raise HarnessError("Prices and budgets must be finite and nonnegative")
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HarnessError("HTTP redirect refused; use the endpoint's final URL")


def request_json(url, payload=None, key=None, timeout=90):
    headers = {"Content-Type": "application/json", "User-Agent": "SpareCode/0.1"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url, data=None if payload is None else
                                 json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as reply:
            body = reply.read(8_000_001)
        if len(body) > 8_000_000:
            raise HarnessError("Provider response exceeds 8 MB")
        data = json.loads(body)
        if not isinstance(data, dict) or data.get("error"):
            raise HarnessError("Provider returned an error or invalid response")
        return data
    except urllib.error.HTTPError as exc:
        # Do not print error bodies: providers can echo submitted code or credentials.
        raise HarnessError(f"Provider HTTP {exc.code}; no automatic retry was made") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HarnessError(f"Provider connection failed ({type(exc).__name__}); "
                           "request may have been billed; no automatic retry") from None
    except (ValueError, UnicodeError):
        raise HarnessError("Provider returned invalid JSON; no automatic retry") from None


def catalog():
    data = request_json(OPENROUTER + "/models")
    if not isinstance(data.get("data"), list):
        raise HarnessError("Invalid model catalog")
    return data["data"]


@dataclass(frozen=True)
class Price:
    input: Decimal  # dollars per token
    output: Decimal

    def cost(self, prompt, completion):
        return self.input * prompt + self.output * completion

    @classmethod
    def from_model(cls, model):
        pricing = model.get("pricing", {})
        # Use the highest tier, not only a promotional/short-context minimum.
        tiers = [pricing] + pricing.get("overrides", [])
        try:
            if any(money(t.get("request", 0)) for t in tiers):
                raise HarnessError("Per-request-priced models are not supported")
            return cls(max(money(t["prompt"]) for t in tiers),
                       max(money(t["completion"]) for t in tiers))
        except (KeyError, TypeError):
            raise HarnessError("Model has no usable token prices") from None


class Ledger:
    def __init__(self, price, budget="0.25", max_tokens=120_000):
        self.price = price
        self.budget = money(budget)
        self.max_tokens = max_tokens
        self.accounted = Decimal(0)
        self.charged_tokens = 0
        self.requests = []

    def reserve(self, messages, max_output):
        # Bytes are deliberately conservative for common byte-based tokenizers.
        # Extra allowance covers chat framing; this is NOT a tokenizer/billing guarantee.
        prompt_bound = len(json.dumps(messages, ensure_ascii=False).encode()) + 1024
        cost = self.price.cost(prompt_bound, max_output)
        if self.accounted + cost > self.budget:
            raise HarnessError("Budget stop: the next request's reservation would exceed the allowance")
        if self.charged_tokens + prompt_bound + max_output > self.max_tokens:
            raise HarnessError("Token stop: the next request would exceed the conservative token allowance")
        entry = {"prompt_bound": prompt_bound, "output_limit": max_output,
                 "reserved_usd": str(cost), "accounted_usd": str(cost),
                 "status": "reserved", "tokens": prompt_bound + max_output}
        self.requests.append(entry)
        self.accounted += cost
        self.charged_tokens += entry["tokens"]
        return entry

    def settle(self, entry, usage):
        if not isinstance(usage, dict):
            entry["status"] = "usage_missing_reservation_kept"
            return
        p, c = usage.get("prompt_tokens"), usage.get("completion_tokens")
        if not all(type(v) is int and v >= 0 for v in (p, c)):
            entry["status"] = "usage_missing_reservation_kept"
            if usage.get("cost") is not None:
                reported = money(usage["cost"])
                entry["reported_cost_usd"] = str(reported)
                accounted = max(money(entry["accounted_usd"]), reported)
                self.accounted += accounted - money(entry["accounted_usd"])
                entry["accounted_usd"] = str(accounted)
                if self.accounted > self.budget:
                    raise HarnessError("Reported cost exceeded the budget; stopping")
            return
        cost = self.price.cost(p, c)
        if usage.get("cost") is not None:
            reported = money(usage["cost"])
            entry["reported_cost_usd"] = str(reported)
            cost = max(cost, reported)
        self.accounted += cost - money(entry["accounted_usd"])
        self.charged_tokens += p + c - entry["tokens"]
        entry.update(status="usage_received", prompt_tokens=p, completion_tokens=c,
                     accounted_usd=str(cost), tokens=p + c)
        if p > entry["prompt_bound"] or c > entry["output_limit"]:
            raise HarnessError("Provider exceeded the request's token estimate/limit; stopping")
        if self.accounted > self.budget:
            raise HarnessError("Reported cost exceeded the budget; stopping")

    def summary(self):
        return {"budget_usd": str(self.budget), "accounted_usd": str(self.accounted),
                "accounted_tokens": self.charged_tokens, "requests": self.requests,
                "input_usd_per_million": str(self.price.input * 1_000_000),
                "output_usd_per_million": str(self.price.output * 1_000_000)}


class Provider:
    def __init__(self, kind="openrouter", model=None, base_url=None,
                 key_env=None, input_price=None, output_price=None):
        self.kind = kind
        if kind == "compatible" and (not base_url or not model):
            raise HarnessError("Compatible mode requires --base-url and --model")
        self.model = model or (DEFAULT_MODEL if kind == "openrouter" else "qwen2.5-coder:3b")
        self.base_url = (base_url or (OPENROUTER if kind == "openrouter" else
                                    "http://127.0.0.1:11434/v1")).rstrip("/")
        parsed = urllib.parse.urlsplit(self.base_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise HarnessError("Endpoint must not contain credentials, query, or fragment")
        try:
            loopback = parsed.hostname == "localhost" or ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            loopback = False
        if parsed.scheme not in ("https", "http") or not parsed.hostname:
            raise HarnessError("Invalid endpoint URL")
        if parsed.scheme != "https" and not loopback:
            raise HarnessError("Non-local endpoints require HTTPS")
        if kind == "openrouter" and self.base_url != OPENROUTER:
            raise HarnessError("Use --provider compatible for a custom endpoint")
        if kind == "local" and not loopback:
            raise HarnessError("Local mode requires a loopback endpoint")
        if kind == "local" and ("cloud" in self.model.lower() or "/" in self.model):
            raise HarnessError("Local mode refuses cloud/routed model IDs")
        self.key_env = key_env or ("OPENROUTER_API_KEY" if kind == "openrouter" else "SPARECODE_API_KEY")
        self.key = None if kind == "local" else os.environ.get(self.key_env)
        if kind != "local" and not self.key:
            raise HarnessError(f"Set {self.key_env} in your shell; credentials are never stored by SpareCode")
        self.context_length = 32768
        if kind == "openrouter":
            model_info = next((m for m in catalog() if m.get("id") == self.model), None)
            if not model_info:
                raise HarnessError("Model is absent from the current catalog; use 'sparecode models'")
            if "response_format" not in model_info.get("supported_parameters", []):
                raise HarnessError("Choose a model supporting response_format for the JSON action protocol")
            self.price = Price.from_model(model_info)
            self.context_length = int(model_info["context_length"])
        elif kind == "local":
            self.price = Price(Decimal(0), Decimal(0))
        else:
            if input_price is None or output_price is None:
                raise HarnessError("Compatible endpoints require --input-price and --output-price in USD per million")
            self.price = Price(money(input_price) / 1_000_000, money(output_price) / 1_000_000)

    def complete(self, messages, max_output):
        body = {"model": self.model, "messages": messages, "max_tokens": max_output,
                "temperature": 0.1, "stream": False,
                "response_format": {"type": "json_object"}}
        if self.kind == "openrouter":
            body["provider"] = {"sort": "price", "data_collection": "deny",
                                "require_parameters": True, "allow_fallbacks": False,
                                "max_price": {"prompt": float(self.price.input * 1_000_000),
                                              "completion": float(self.price.output * 1_000_000),
                                              "request": 0}}
        return request_json(self.base_url + "/chat/completions", body, self.key)
