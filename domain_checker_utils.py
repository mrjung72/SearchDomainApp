import argparse
import csv
import itertools
import re
import string
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import dns.resolver

MAX_WORKERS = 30  # 동시 조회 스레드 수 (네트워크 상태에 맞게 조절)
DEFAULT_MAX_LENGTH = 3


def create_resolver() -> dns.resolver.Resolver:
    resolver = dns.resolver.Resolver()
    resolver.nameservers = ["8.8.8.8", "1.1.1.1", "9.9.9.9"]
    resolver.lifetime = 2.0
    resolver.timeout = 2.0
    return resolver
