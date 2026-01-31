import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import aiohttp

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 4.0
_MAX_HTML_BYTES = 200_000

_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

_WAF_HEADER_MARKERS = {
    "perimeterx": ("x-px", "x-perimeterx", "x-px-debug"),
    "cloudflare": ("cf-ray", "cf-cache-status", "cf-apo-via"),
    "imperva": ("x-iinfo", "x-cdn", "x-cdn-geo", "incap-"),
    "akamai": ("akamai", "akamai-ghost", "akamai-grn"),
    "sucuri": ("x-sucuri-id", "x-sucuri-cache"),
    "fastly": ("x-fastly-request-id", "fastly-debug"),
    "cloudfront": ("x-amz-cf-id", "x-amz-cf-pop"),
    "aws-waf": ("x-amzn-waf-action",),
    "azure-front-door": ("x-azure-ref", "x-fd-int-roxy-purgeid", "x-fd-traffic"),
    "f5": ("x-wa-info", "x-cnection", "x-asm", "x-waf-event-info"),
    "barracuda": ("barra", "x-barracuda", "bnc"),  # common header fragments
    "datadome": ("x-datadome",),
    "distil": ("x-distil-cs", "x-distil-debug"),
    "radware": ("x-sl-compstate", "x-sl-edge", "x-sl-referrer"),
    "reblaze": ("x-reblaze", "rbzid"),
    "stackpath": ("x-sucuri-id", "x-sucuri-cache", "x-stackpath"),
    "stackpath-waf": ("x-stackpath", "spmsg", "sprequestguid"),
    "siteground": ("x-proxy-cache", "x-hw", "sg-"),
    "varnish-waf": ("x-varnish", "x-cache"),
}

_WAF_HTML_MARKERS = {
    "perimeterx": (
        "captcha.perimeterx.net",
        "perimeterx",
        "px-captcha",
        "px-block",
        "pxBlock",
        "px-cdn",
    ),
    "cloudflare": ("cf-browser-verification", "cloudflare", "/cdn-cgi/"),
    "imperva": ("incapsula", "imperva", "x2cap", "incap_ses"),
    "datadome": ("datadome", "geo.captcha-delivery.com"),
    "distil": ("distil networks", "distil_r_captcha", "distilr", "distilcaptcha"),
    "kasada": ("kasada", "kpsdk"),
    "radware": ("rbz", "radware", "appwall"),
    "reblaze": ("reblaze", "rbz"),
    "sucuri": ("sucuri firewall", "sucuri cloudproxy"),
    "f5": ("asm", "big-ip", "f5", "x-waf-event-info"),
    "modsecurity": ("mod_security", "modsecurity", "modsecurity rules"),
}

_TECH_HEADER_MARKERS = {
    "wordpress": ("x-powered-by:wordpress", "x-generator:wordpress"),
    "shopify": ("x-shopify-", "x-sorting-hat-podid", "x-sorting-hat-shopid"),
    "magento": ("x-magento-", "x-ua-compatible:magento"),
    "drupal": ("x-generator:drupal", "x-drupal-cache"),
    "joomla": ("x-generator:joomla",),
    "wix": ("x-wix-request-id",),
    "squarespace": ("x-sqsp-cache", "x-squarespace-cache"),
    "webflow": ("x-wf-request-id",),
    "ghost": ("x-ghost-cache",),
    "nextjs": ("x-powered-by:next.js",),
    "nuxt": ("x-powered-by:nuxt",),
    "express": ("x-powered-by:express",),
    "django": ("csrftoken", "x-frame-options:sameorigin"),
    "laravel": ("laravel_session",),
    "rails": ("x-runtime", "x-rails", "_rails"),
}

_TECH_HTML_MARKERS = {
    "wordpress": (
        "wp-content/",
        "wp-includes/",
        "wp-json",
        "xmlrpc.php",
        'content="wordpress',
    ),
    "shopify": (
        "cdn.shopify.com",
        "x-shopify-stage",
        "shopify-section",
        "shopify-buy-button",
    ),
    "magento": (
        "mage/",
        "magento",
        "catalog/product/view",
        "data-mage-init",
    ),
    "drupal": ("drupal-settings-json", "drupal", "data-drupal"),
    "joomla": ("joomla", "com_content", 'content="joomla'),
    "wix": ("wix.com", "wixsite", "wix-code-sdk"),
    "squarespace": ("static.squarespace.com", "squarespace"),
    "webflow": ("webflow.com", "data-wf-page", "data-wf-site"),
    "ghost": ("ghost.io", 'content="ghost'),
    "nextjs": ("_next/static", "nextjs", "__next_data__"),
    "nuxt": ("_nuxt/", "__nuxt", "nuxt"),
    "react": ("data-reactroot", "data-reactid"),
    "vue": ("data-v-", 'id="app"'),
    "angular": ("ng-version", "ng-app", "ng-controller"),
    "svelte": ("svelte", "__svelte", "data-svelte"),
    "django": ("csrftoken", "django", "data-csrf"),
    "laravel": ("laravel", "csrf-token"),
    "rails": ("rails", "csrf-param", "csrf-token"),
    "aspnet": ("__viewstate", "asp.net", "x-aspnet-version"),
}

_CAPTCHA_HTML_MARKERS = {
    "recaptcha": (
        "www.google.com/recaptcha/api.js",
        "www.recaptcha.net/recaptcha/api.js",
        "g-recaptcha",
        "grecaptcha",
        "data-sitekey",
    ),
    "hcaptcha": (
        "js.hcaptcha.com/1/api.js",
        "h-captcha",
        "hcaptcha",
        "data-sitekey",
    ),
    "turnstile": (
        "challenges.cloudflare.com/turnstile/v0/api.js",
        "cf-turnstile",
        "turnstile.render",
    ),
    "arkose": (
        "client-api.arkoselabs.com",
        "arkoselabs",
        "funcaptcha",
        "fc-token",
        "data-pkey",
    ),
    "geetest": (
        "static.geetest.com",
        "geetest",
        "gt4.js",
        "gt_captcha",
    ),
    "friendlycaptcha": (
        "friendlycaptcha",
        "friendly-challenge",
        "cdn.jsdelivr.net/npm/friendly-challenge",
    ),
    "keycaptcha": ("keycaptcha", "keycaptcha.com"),
    "honeycaptcha": ("honeycaptcha",),
    "textcaptcha": ("textcaptcha",),
}


@dataclass(frozen=True)
class ReconReport:
    url: str
    headers: Dict[str, str]
    html_sample: str
    waf_hits: Tuple[str, ...]
    tech_hits: Tuple[str, ...]
    captcha_hits: Tuple[str, ...]


def preflight_recon(
    url: str,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    max_html_bytes: int = _MAX_HTML_BYTES,
) -> ReconReport:
    return asyncio.run(preflight_recon_async(url, timeout_seconds, max_html_bytes))


async def preflight_recon_async(
    url: str,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    max_html_bytes: int = _MAX_HTML_BYTES,
) -> ReconReport:
    headers: Dict[str, str] = {}
    html_sample = ""

    try:
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": _USER_AGENT}) as session:
            async with session.get(url) as response:
                headers = {key.lower(): value for key, value in response.headers.items()}
                text = await response.text(errors="ignore")
                html_sample = text[:max_html_bytes]
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        logger.debug("Recon preflight failed for %s: %s", url, exc)

    waf_hits = detect_waf(headers, html_sample)
    tech_hits = detect_tech(headers, html_sample)
    captcha_hits = detect_captcha(headers, html_sample)

    if tech_hits:
        logger.info("Tech detected for %s: %s", url, ", ".join(tech_hits))

    return ReconReport(
        url=url,
        headers=headers,
        html_sample=html_sample,
        waf_hits=waf_hits,
        tech_hits=tech_hits,
        captcha_hits=captcha_hits,
    )


def detect_waf(headers: Dict[str, str], html_sample: str) -> Tuple[str, ...]:
    hits = set()
    lower_headers = {key.lower(): value for key, value in headers.items()}
    header_blob = " ".join(f"{k}:{v}".lower() for k, v in lower_headers.items())
    html_blob = html_sample.lower()

    for waf_name, markers in _WAF_HEADER_MARKERS.items():
        if _contains_any_marker(header_blob, markers):
            hits.add(waf_name)

    for waf_name, markers in _WAF_HTML_MARKERS.items():
        if _contains_any_marker(html_blob, markers):
            hits.add(waf_name)

    return tuple(sorted(hits))


def detect_tech(headers: Dict[str, str], html_sample: str) -> Tuple[str, ...]:
    hits = set()
    html_blob = html_sample.lower()
    header_blob = " ".join(f"{k}:{v}".lower() for k, v in headers.items())

    for tech_name, markers in _TECH_HTML_MARKERS.items():
        if _contains_any_marker(html_blob, markers):
            hits.add(tech_name)

    for tech_name, markers in _TECH_HEADER_MARKERS.items():
        if _contains_any_marker(header_blob, markers):
            hits.add(tech_name)

    return tuple(sorted(hits))


def detect_captcha(headers: Dict[str, str], html_sample: str) -> Tuple[str, ...]:
    hits = set()
    html_blob = html_sample.lower()

    for captcha_name, markers in _CAPTCHA_HTML_MARKERS.items():
        if _contains_any_marker(html_blob, markers):
            hits.add(captcha_name)

    return tuple(sorted(hits))


def _contains_any_marker(blob: str, markers: Iterable[str]) -> bool:
    for marker in markers:
        if marker in blob:
            return True
    return False
