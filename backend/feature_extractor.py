from __future__ import annotations

import math
import re
import hashlib
from domain_parts import domain_parts
from urllib.parse import parse_qs, unquote, urlparse, urlunparse
from reference_origin_features import reference_origin_match

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

FEATURE_SCHEMA_VERSION = "url-v4-public-suffix"
LEGACY_FEATURE_SCHEMA_VERSION = "url-v3-www-canonical"
QUERY_ROBUST_SCHEMA_VERSION = "url-v5-query-structural"
HOST_CONTEXT_SCHEMA_VERSION = "url-v6-host-context"
DOMAIN_LEXICAL_SCHEMA_VERSION = "url-v7-domain-lexical"
DOMAIN_ENRICHED_SCHEMA_VERSION = "url-v8-domain-enriched"
REFERENCE_ORIGIN_SCHEMA_VERSION = "url-v9-reference-origin"
REFERENCE_ROOT_SCHEMA_VERSION = "url-v10-reference-root-context"

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

# Query length/count are kept for audit, but not supplied to this model: the
# publisher strips benign queries, making these two fields a source shortcut.
QUERY_ROBUST_FEATURE_NAMES = [name for name in FEATURE_NAMES if name not in {'query_length', 'num_params'}]
HOST_CONTEXT_FEATURE_NAMES = [name for name in QUERY_ROBUST_FEATURE_NAMES
    if name not in {'hostname_length', 'hostname_entropy', 'max_hostname_label_length', 'num_dots', 'url_length'}] + [
    'registered_domain_length', 'registered_domain_entropy', 'registered_label_length',
    'structural_path_url_length', 'subdomain_suspicious_word_count', 'subdomain_has_punycode',
    'subdomain_digit_ratio', 'subdomain_max_label_length', 'subdomain_label_count',
]
DOMAIN_LEXICAL_FEATURE_NAMES = HOST_CONTEXT_FEATURE_NAMES + [f'domain_ngram_{i:03}' for i in range(128)]
DOMAIN_ENRICHED_FEATURE_NAMES = QUERY_ROBUST_FEATURE_NAMES + [name for name in DOMAIN_LEXICAL_FEATURE_NAMES if name not in QUERY_ROBUST_FEATURE_NAMES] + ['enhanced_credential_parameter_count', 'enhanced_redirect_parameter_count', 'token_suspicious_word_count']
REFERENCE_ORIGIN_FEATURE_NAMES = DOMAIN_ENRICHED_FEATURE_NAMES + ['publisher_reference_origin_match']
REFERENCE_ROOT_FEATURE_NAMES = REFERENCE_ORIGIN_FEATURE_NAMES + ['publisher_reference_root_context']


def feature_names(schema: str) -> list[str]:
    if schema == REFERENCE_ROOT_SCHEMA_VERSION:
        return REFERENCE_ROOT_FEATURE_NAMES
    if schema == REFERENCE_ORIGIN_SCHEMA_VERSION:
        return REFERENCE_ORIGIN_FEATURE_NAMES
    if schema == DOMAIN_ENRICHED_SCHEMA_VERSION:
        return DOMAIN_ENRICHED_FEATURE_NAMES
    if schema == DOMAIN_LEXICAL_SCHEMA_VERSION:
        return DOMAIN_LEXICAL_FEATURE_NAMES
    if schema == HOST_CONTEXT_SCHEMA_VERSION:
        return HOST_CONTEXT_FEATURE_NAMES
    return QUERY_ROBUST_FEATURE_NAMES if schema == QUERY_ROBUST_SCHEMA_VERSION else FEATURE_NAMES

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

def reference_root_sensitive_query(raw_url: str) -> bool:
    if '?' not in raw_url: return False
    parsed = urlparse(normalize_url(raw_url))
    sensitive = CREDENTIAL_PARAMETER_NAMES | REDIRECT_PARAMETER_NAMES | {
        'email','username','user','access','code','state','client','clientid','app','appid','scope','response','csrf',
    }
    for name in parse_qs(parsed.query, keep_blank_values=True):
        key = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', unquote(name))
        if set(re.findall(r'[a-z0-9]+', key.casefold())) & sensitive:
            return True
    return False


def reference_root_context(features: dict[str, float], raw_url: str = '') -> float:
    """An observable entry-URL context, not an assertion of content safety."""
    root = (features['publisher_reference_origin_match'] == 1 and features['path_depth'] == 0
            and features['path_length'] <= 1)
    hazards = ('has_nested_url', 'has_encoded_url', 'has_at_symbol', 'has_backslash',
               'redirect_parameter_count', 'credential_parameter_count',
               'enhanced_redirect_parameter_count', 'enhanced_credential_parameter_count')
    return float(root and all(features[name] == 0 for name in hazards) and not reference_root_sensitive_query(raw_url))


def extract_features(raw_url: str, schema: str = FEATURE_SCHEMA_VERSION) -> dict[str, float]:
    if schema == REFERENCE_ROOT_SCHEMA_VERSION:
        features = extract_features(raw_url, REFERENCE_ORIGIN_SCHEMA_VERSION)
        features['publisher_reference_root_context'] = reference_root_context(features, raw_url)
        return features
    if schema == REFERENCE_ORIGIN_SCHEMA_VERSION:
        features = extract_features(raw_url, DOMAIN_ENRICHED_SCHEMA_VERSION)
        features['publisher_reference_origin_match'] = reference_origin_match(normalize_url(raw_url))
        return features
    if schema == DOMAIN_ENRICHED_SCHEMA_VERSION:
        features = extract_features(raw_url, DOMAIN_LEXICAL_SCHEMA_VERSION)
        original = extract_features(raw_url, QUERY_ROBUST_SCHEMA_VERSION)
        features['enhanced_credential_parameter_count'] = features['credential_parameter_count']
        features['enhanced_redirect_parameter_count'] = features['redirect_parameter_count']
        features['token_suspicious_word_count'] = features['suspicious_word_count']
        # The leading 32 columns stay exactly compatible with the operating RF;
        # newly trained trees can additionally use root-domain character context.
        for name in QUERY_ROBUST_FEATURE_NAMES:
            features[name] = original[name]
        return features
    if schema == DOMAIN_LEXICAL_SCHEMA_VERSION:
        features = extract_features(raw_url, HOST_CONTEXT_SCHEMA_VERSION)
        parsed = urlparse(normalize_url(raw_url))
        host = (parsed.hostname or '').lower().rstrip('.').removeprefix('www.').encode('idna').decode('ascii')
        registered, label, count = domain_parts(host)
        subdomain = host[:-len(registered)].rstrip('.') if registered else ''
        parts = subdomain.split('.') if subdomain else []
        # V7 explicitly uses canonical IDNA for subdomain slicing; V6 artifacts
        # retain their original extraction unchanged.
        features.update({
            'subdomain_suspicious_word_count': float(sum(word in subdomain for word in SUSPICIOUS_WORDS)),
            'subdomain_has_punycode': float(any(part.startswith('xn--') for part in parts)),
            'subdomain_digit_ratio': sum(char.isdigit() for char in subdomain) / max(1, len(subdomain)),
            'subdomain_max_label_length': float(max(map(len, parts), default=0)),
            'subdomain_label_count': float(count),
        })
        for i in range(128):
            features[f'domain_ngram_{i:03}'] = 0.0
        text = '^' + label + '$'
        # Binary hashed 2/3/4-grams, applied to every registered-domain label.
        # No list of brands, fixed score, or runtime domain exception.
        for size in (2, 3, 4):
            for i in range(len(text) - size + 1):
                digest = hashlib.blake2s(text[i:i+size].encode('ascii'), digest_size=2).digest()
                bucket = int.from_bytes(digest, 'little') % 128
                features[f'domain_ngram_{bucket:03}'] = 1.0
        return features
    if schema == HOST_CONTEXT_SCHEMA_VERSION:
        features = extract_features(raw_url, QUERY_ROBUST_SCHEMA_VERSION)
        parsed = urlparse(normalize_url(raw_url))
        hostname = (parsed.hostname or '').lower().rstrip('.').removeprefix('www.')
        registered, label, count = domain_parts(hostname)
        subdomain = hostname[:-len(registered)].rstrip('.') if registered else ''
        labels = subdomain.split('.') if subdomain else []
        features.update({
            'registered_domain_length': float(len(registered)),
            'registered_domain_entropy': shannon_entropy(registered),
            'registered_label_length': float(len(label)),
            'structural_path_url_length': float(len(parsed.scheme) + 3 + len(registered) + len(parsed.path)),
            'subdomain_suspicious_word_count': float(sum(word in subdomain for word in SUSPICIOUS_WORDS)),
            'subdomain_has_punycode': float(any(part.startswith('xn--') for part in labels)),
            'subdomain_digit_ratio': sum(char.isdigit() for char in subdomain) / max(1, len(subdomain)),
            'subdomain_max_label_length': float(max(map(len, labels), default=0)),
            'subdomain_label_count': float(count),
        })
        # Match meaningful URL tokens, so author/shopping-style substrings are
        # not credential evidence. Query values remain excluded as in v5.
        tokens = set(re.findall(r'[a-z0-9]+', unquote(hostname + parsed.path).casefold()))
        features['suspicious_word_count'] = float(sum(word in tokens for word in SUSPICIOUS_WORDS))
        parameter_names = {name.casefold() for name in parse_qs(parsed.query, keep_blank_values=True)}
        features['credential_parameter_count'] = float(len(parameter_names & CREDENTIAL_PARAMETER_NAMES))
        features['redirect_parameter_count'] = float(len(parameter_names & REDIRECT_PARAMETER_NAMES))
        return features
    if schema == QUERY_ROBUST_SCHEMA_VERSION:
        url = normalize_url(raw_url)
        parsed = urlparse(url)
        # All domains follow the same extraction; no brand whitelist or score cap.
        # Host/path still supply structural signals. Query URL/redirect/credential
        # signals remain observable rather than discarding every query as safe.
        structural_url = urlunparse(parsed._replace(query='', fragment=''))
        structural = extract_features(structural_url, FEATURE_SCHEMA_VERSION)
        original = extract_features(url, FEATURE_SCHEMA_VERSION)
        for name in ('query_length', 'num_params', 'has_nested_url', 'has_encoded_url',
                     'redirect_parameter_count', 'credential_parameter_count'):
            structural[name] = original[name]
        return structural
    if schema not in {FEATURE_SCHEMA_VERSION, LEGACY_FEATURE_SCHEMA_VERSION}:
        raise ValueError(f"Unsupported feature schema: {schema}; retrain the model")
    url = normalize_url(raw_url)
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    # A leading www label is a presentation alias, not meaningful phishing
    # evidence. Canonicalizing it prevents dataset-source formatting from
    # becoming a shortcut learned by the model.
    feature_hostname = hostname.removeprefix("www.")
    www_prefix_length = len(hostname) - len(feature_hostname)
    path = parsed.path or ""
    query = parsed.query or ""
    decoded_url = unquote(url).lower()
    host_parts = [part for part in feature_hostname.split(".") if part]
    tld = host_parts[-1] if host_parts else ""
    domain_label = host_parts[-2] if len(host_parts) >= 2 else (host_parts[0] if host_parts else "")
    subdomain_count = max(0, len(host_parts) - 2)
    if schema == FEATURE_SCHEMA_VERSION:
        registered, domain_label, subdomain_count = domain_parts(feature_hostname)
    params = parse_qs(query)
    parameter_names = {name.casefold() for name in params}

    has_ip_host = bool(re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", feature_hostname))
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
        sum(char.isdigit() for char in feature_hostname) / len(feature_hostname)
        if feature_hostname
        else 0.0
    )
    domain_vowel_ratio = (
        sum(char in "aeiou" for char in domain_label) / len(domain_label)
        if domain_label
        else 0.0
    )

    return {
        "url_length": float(len(url) - www_prefix_length),
        "hostname_length": float(len(feature_hostname)),
        "path_length": float(len(path)),
        "query_length": float(len(query)),
        "num_dots": float(url.count(".") - (1 if www_prefix_length else 0)),
        "num_hyphens": float(url.count("-")),
        "num_digits": float(sum(char.isdigit() for char in url)),
        "num_slashes": float(url.count("/")),
        "num_params": float(len(params)),
        "subdomain_count": float(subdomain_count),
        "has_https": 1.0 if parsed.scheme == "https" else 0.0,
        "has_ip_host": 1.0 if has_ip_host else 0.0,
        "has_at_symbol": 1.0 if "@" in url else 0.0,
        "has_encoded_url": 1.0 if has_encoded_url else 0.0,
        "has_nested_url": 1.0 if has_nested_url else 0.0,
        "is_shortener": 1.0 if feature_hostname in SHORTENERS else 0.0,
        "risky_tld": 1.0 if tld in RISKY_TLDS else 0.0,
        "suspicious_word_count": float(suspicious_word_count),
        "hostname_entropy": float(shannon_entropy(feature_hostname)),
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

def feature_vector(raw_url: str, schema: str = FEATURE_SCHEMA_VERSION) -> list[float]:
    features = extract_features(raw_url, schema)
    return [features[name] for name in feature_names(schema)]
