"""Offline ICANN Public Suffix List parsing, shared snapshot with browser rules."""
from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path


@lru_cache(maxsize=1)
def suffix_rules():
    return set(Path(__file__).with_name('public_suffix_list.dat').read_text(encoding='utf-8').split())


def domain_parts(hostname):
    host = hostname.lower().rstrip('.').removeprefix('www.').encode('idna').decode('ascii')
    try:
        ip_address(host.strip('[]'))
        return host, host, 0
    except ValueError:
        pass
    labels = host.split('.') if host else []
    suffix_size = 1
    rules = suffix_rules()
    for i in range(len(labels)):
        tail = '.'.join(labels[i:])
        if '!' + tail in rules:
            suffix_size = len(labels) - i - 1
            break
        if tail in rules or (i + 1 < len(labels) and '*.' + '.'.join(labels[i+1:]) in rules):
            suffix_size = max(suffix_size, len(labels) - i)
    domain_index = len(labels) - suffix_size - 1
    if domain_index < 0:
        return host, '', 0
    return '.'.join(labels[domain_index:]), labels[domain_index], domain_index
