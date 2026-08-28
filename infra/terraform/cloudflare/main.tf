# CDN + WAF in front of nginx/ingress, via Cloudflare (proxied DNS gets you
# both for free on any paid plan). Swap for AWS CloudFront + AWS WAF or
# Fastly if that's already your cloud — the concepts (cache static assets
# at the edge, rate-limit + block known-bad patterns before they reach
# your cluster) are the same either way; this is just one concrete,
# cheap-to-start-with implementation.
#
# Prerequisites: a Cloudflare account + zone for your domain, API token
# with Zone:Edit permissions in CLOUDFLARE_API_TOKEN.

terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }
}

variable "cloudflare_zone_id" {
  type = string
}

variable "api_hostname" {
  type    = string
  default = "api.autoflow.io"
}

variable "app_hostname" {
  type    = string
  default = "app.autoflow.io"
}

variable "origin_ip" {
  description = "Public IP/hostname of your ingress load balancer"
  type        = string
}

# ── DNS, proxied through Cloudflare (this is what turns on CDN + WAF) ──────
resource "cloudflare_record" "api" {
  zone_id = var.cloudflare_zone_id
  name    = var.api_hostname
  type    = "A"
  content = var.origin_ip
  proxied = true
}

resource "cloudflare_record" "app" {
  zone_id = var.cloudflare_zone_id
  name    = var.app_hostname
  type    = "A"
  content = var.origin_ip
  proxied = true
}

# ── WAF: managed ruleset (OWASP-style core rules) ───────────────────────────
resource "cloudflare_ruleset" "waf_managed" {
  zone_id = var.cloudflare_zone_id
  name    = "autoflow-managed-waf"
  kind    = "zone"
  phase   = "http_request_firewall_managed"

  rules {
    action = "execute"
    action_parameters {
      id = "efb7b8c949ac4650a09736fc376e9aee" # Cloudflare Managed Ruleset
    }
    expression  = "true"
    description = "Cloudflare-managed WAF rules (SQLi, XSS, known CVEs)"
  }
}

# ── WAF: custom rule blocking credential-stuffing patterns on /auth/login ──
resource "cloudflare_ruleset" "waf_custom" {
  zone_id = var.cloudflare_zone_id
  name    = "autoflow-custom-waf"
  kind    = "zone"
  phase   = "http_request_firewall_custom"

  rules {
    action      = "challenge"
    expression  = "(http.request.uri.path eq \"/api/auth/login\" and cf.threat_score gt 30)"
    description = "Challenge suspicious login attempts (nginx already rate-limits by IP; this adds device/behavior signal)"
  }

  rules {
    action      = "block"
    expression  = "(cf.threat_score gt 80)"
    description = "Block obviously malicious traffic outright before it reaches the cluster"
  }
}

# ── Edge rate limiting (belt-and-suspenders alongside api/middleware/rate_limit.py) ──
resource "cloudflare_rate_limit" "api_edge" {
  zone_id   = var.cloudflare_zone_id
  threshold = 1200
  period    = 60
  match {
    request {
      url_pattern = "${var.api_hostname}/*"
    }
  }
  action {
    mode    = "challenge"
    timeout = 60
  }
  description = "Edge-level backstop; app-level per-user limiting in api/middleware/rate_limit.py is the primary control"
}

# ── CDN: cache the frontend's static assets, never cache the API ───────────
resource "cloudflare_page_rule" "cache_static_assets" {
  zone_id  = var.cloudflare_zone_id
  target   = "${var.app_hostname}/assets/*"
  priority = 1
  actions {
    cache_level = "cache_everything"
    edge_cache_ttl = 2592000 # 30 days — pair with content-hashed filenames from the frontend build
  }
}

resource "cloudflare_page_rule" "no_cache_api" {
  zone_id  = var.cloudflare_zone_id
  target   = "${var.api_hostname}/*"
  priority = 1
  actions {
    cache_level = "bypass"
  }
}
