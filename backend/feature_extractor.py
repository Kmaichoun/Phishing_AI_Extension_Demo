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

FREE_HOSTING_OR_DDNS = {
    "github.io", "pages.dev", "netlify.app", "vercel.app", "web.app",
    "firebaseapp.com", "duckdns.org", "no-ip.org", "ddns.net",
    "hopto.org", "serveo.net", "ngrok-free.app",
}

REDIRECT_PARAMETER_NAMES = {
    "url", "u", "redirect", "redirect_uri", "next", "target", "to",
    "continue", "return", "returnurl", "dest", "destination",
}

CREDENTIAL_PARAMETER_NAMES = {
    "password", "passwd", "pass", "pwd", "otp", "token", "session",
    "sessionid", "pin", "secret", "seed", "credential", "auth",
}

SUSPICIOUS_FILE_EXTENSIONS = {
    ".exe", ".msi", ".scr", ".bat", ".cmd", ".ps1", ".js", ".jar",
    ".apk", ".dmg", ".pkg", ".iso",
}

ARCHIVE_FILE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz"}

FEATURE_SCHEMA_VERSION = "url-v2"

FEATURE_NAMES = [
    "url_length", "hostname_length", "path_length", "query_length",
    "num_dots", "num_hyphens", "num_digits", "num_slashes", "num_params",
    "subdomain_count", "has_https", "has_ip_host", "has_at_symbol",
    "has_encoded_url", "has_nested_url", "is_shortener", "risky_tld",
    "suspicious_word_count", "hostname_entropy", "path_depth",
    "max_hostname_label_length", "tld_length", "num_underscores",
    "percent_encoding_count", "has_punycode", "has_backslash",
    "has_non_ascii", "redirect_parameter_count",
    "credential_parameter_count", "has_suspicious_file",
    "has_archive_file", "uses_free_hosting_or_ddns", "hostname_digit_ratio",
    "domain_vowel_ratio",
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


def is_same_or_subdomain(hostname: str, domain: str) -> bool:
    host = hostname.removeprefix("www.").lower()
    candidate = domain.removeprefix("www.").lower()
    return host == candidate or host.endswith("." + candidate)

def extract_features(raw_url: str) -> dict[str, float]:
    url = normalize_url(raw_url)
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path or ""
    query = parsed.query or ""
    decoded_url = unquote(url).lower()
    host_parts = [part for part in hostname.split(".") if part]
    tld = host_parts[-1] if host_parts else ""
    domain_label = host_parts[-2] if len(host_parts) >= 2 else (host_parts[0] if host_parts else "")
    params = parse_qs(query)
    parameter_names = {name.casefold() for name in params}

    has_ip_host = bool(re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", hostname))
    body_without_scheme = re.sub(r"^https?://", "", decoded_url)
    has_nested_url = "http://" in body_without_scheme or "https://" in body_without_scheme
    has_encoded_url = "%2f" in url.lower() or "%3a" in url.lower()
    suspicious_word_count = sum(1 for word in SUSPICIOUS_WORDS if word in decoded_url)
    path_lower = path.casefold()
    path_depth = len([part for part in path.split("/") if part])
    redirect_parameter_count = sum(
        1 for name in parameter_names if name in REDIRECT_PARAMETER_NAMES
    )
    credential_parameter_count = sum(
        1 for name in parameter_names if name in CREDENTIAL_PARAMETER_NAMES
    )
    hostname_digit_ratio = (
        sum(char.isdigit() for char in hostname) / len(hostname) if hostname else 0.0
    )
    domain_vowel_ratio = (
        sum(char in "aeiou" for char in domain_label) / len(domain_label)
        if domain_label
        else 0.0
    )

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
        "path_depth": float(path_depth),
        "max_hostname_label_length": float(max(map(len, host_parts), default=0)),
        "tld_length": float(len(tld)),
        "num_underscores": float(url.count("_")),
        "percent_encoding_count": float(len(re.findall(r"%[0-9a-fA-F]{2}", url))),
        "has_punycode": 1.0 if any(part.startswith("xn--") for part in host_parts) else 0.0,
        "has_backslash": 1.0 if "\\" in raw_url else 0.0,
        "has_non_ascii": 1.0 if any(ord(char) > 127 for char in raw_url) else 0.0,
        "redirect_parameter_count": float(redirect_parameter_count),
        "credential_parameter_count": float(credential_parameter_count),
        "has_suspicious_file": (
            1.0 if any(path_lower.endswith(ext) for ext in SUSPICIOUS_FILE_EXTENSIONS) else 0.0
        ),
        "has_archive_file": (
            1.0 if any(path_lower.endswith(ext) for ext in ARCHIVE_FILE_EXTENSIONS) else 0.0
        ),
        "uses_free_hosting_or_ddns": (
            1.0
            if any(is_same_or_subdomain(hostname, domain) for domain in FREE_HOSTING_OR_DDNS)
            else 0.0
        ),
        "hostname_digit_ratio": float(hostname_digit_ratio),
        "domain_vowel_ratio": float(domain_vowel_ratio),
    }

def feature_vector(raw_url: str) -> list[float]:
    features = extract_features(raw_url)
    return [features[name] for name in FEATURE_NAMES]
