from __future__ import annotations

import math
import re
from urllib.parse import parse_qs, unquote, urlparse

SUSPICIOUS_WORDS = [
    "login", "signin", "verify", "verification", "secure", "security",
    "account", "update", "confirm", "password", "otp", "2fa", "token",
    "wallet", "banking", "payment", "billing", "kyc", "unlock",
    "suspended", "locked", "urgent", "claim", "reward", "bonus",
]

RISKY_TLDS = {
    "zip", "mov", "top", "xyz", "click", "link", "gq", "tk", "ml",
    "cf", "cfd", "work", "quest", "monster", "icu", "buzz",
}

SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly",
    "rebrand.ly", "ow.ly", "s.id", "lnkd.in", "rb.gy",
}

FEATURE_NAMES = [
    "url_length", "hostname_length", "path_length", "query_length",
    "num_dots", "num_hyphens", "num_digits", "num_slashes", "num_params",
    "subdomain_count", "has_https", "has_ip_host", "has_at_symbol",
    "has_encoded_url", "has_nested_url", "is_shortener", "risky_tld",
    "suspicious_word_count", "hostname_entropy",
]

def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {}
    for char in value:
        counts[char] = counts.get(char, 0) + 1
    entropy = 0.0
    for count in counts.values():
        p = count / len(value)
        entropy -= p * math.log2(p)
    return entropy

def normalize_url(raw_url: str) -> str:
    value = (raw_url or "").strip()
    if not value:
        return "https://example.com"
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", value):
        value = "https://" + value
    return value

def extract_features(raw_url: str) -> dict[str, float]:
    url = normalize_url(raw_url)
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path or ""
    query = parsed.query or ""
    decoded_url = unquote(url).lower()
    host_parts = [part for part in hostname.split(".") if part]
    tld = host_parts[-1] if host_parts else ""
    params = parse_qs(query)

    has_ip_host = bool(re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", hostname))
    body_without_scheme = re.sub(r"^https?://", "", decoded_url)
    has_nested_url = "http://" in body_without_scheme or "https://" in body_without_scheme
    has_encoded_url = "%2f" in url.lower() or "%3a" in url.lower()
    suspicious_word_count = sum(1 for word in SUSPICIOUS_WORDS if word in decoded_url)

    return {
        "url_length": float(len(url)),
        "hostname_length": float(len(hostname)),
        "path_length": float(len(path)),
        "query_length": float(len(query)),
        "num_dots": float(url.count(".")),
        "num_hyphens": float(url.count("-")),
        "num_digits": float(sum(char.isdigit() for char in url)),
        "num_slashes": float(url.count("/")),
        "num_params": float(len(params)),
        "subdomain_count": float(max(0, len(host_parts) - 2)),
        "has_https": 1.0 if parsed.scheme == "https" else 0.0,
        "has_ip_host": 1.0 if has_ip_host else 0.0,
        "has_at_symbol": 1.0 if "@" in url else 0.0,
        "has_encoded_url": 1.0 if has_encoded_url else 0.0,
        "has_nested_url": 1.0 if has_nested_url else 0.0,
        "is_shortener": 1.0 if hostname in SHORTENERS else 0.0,
        "risky_tld": 1.0 if tld in RISKY_TLDS else 0.0,
        "suspicious_word_count": float(suspicious_word_count),
        "hostname_entropy": float(shannon_entropy(hostname)),
    }

def feature_vector(raw_url: str) -> list[float]:
    features = extract_features(raw_url)
    return [features[name] for name in FEATURE_NAMES]
