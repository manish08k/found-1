"""
AutoFlow – Central configuration
All secrets come from environment variables.
Operators register their own OAuth apps once (in .env / docker secrets);
end-users never touch credentials — they just click "Connect".
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ──────────────────────────────────────────────────────────
    APP_NAME: str = "AutoFlow"
    APP_ENV: str = "production"
    APP_BASE_URL: str = "http://localhost:8000"
    # Where the SPA is served. In production this is usually the same as
    # APP_BASE_URL (served behind the same nginx/domain). In local dev the
    # frontend runs on a separate Vite dev server port.
    FRONTEND_URL: str = ""
    APP_SECRET_KEY: str = Field(..., min_length=32)
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://autoflow:autoflow@localhost:5432/autoflow"
    DATABASE_URL_REPLICA: str = ""  # optional — falls back to DATABASE_URL if unset
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40

    # Envelope encryption for credentials (credentials/envelope.py).
    # "local" wraps per-credential data keys with CREDENTIAL_ENCRYPTION_KEY
    # (no extra setup, still gets per-credential DEKs + org-scoped AAD).
    # "aws-kms" wraps them with a real KMS CMK — the master key never
    # leaves AWS. Set CREDENTIAL_KMS_KEY_ID when using aws-kms.
    CREDENTIAL_KMS_PROVIDER: str = "local"  # "local" | "aws-kms"
    CREDENTIAL_KMS_KEY_ID: str = ""
    AWS_REGION: str = "us-east-1"

    # ── Redis / Celery ────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Credential encryption (AES-256-GCM) ──────────────────────────
    CREDENTIAL_ENCRYPTION_KEY: str = Field(..., min_length=32)

    # ── OAuth – Google ────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # ── Platform billing (Stripe) ─────────────────────────────────────
    # This is AutoFlow's OWN Stripe merchant account for subscription
    # billing (upgrading a plan) — distinct from integrations/stripe_/
    # handler.py, which lets a workflow use each USER's own connected
    # Stripe account for payment automation. Two different Stripe
    # relationships; don't confuse the credential/key for one with the
    # other. Empty by default — /api/billing/checkout refuses to create
    # a real checkout session without STRIPE_SECRET_KEY set, rather than
    # silently pretending to succeed.
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID_STARTER: str = ""
    STRIPE_PRICE_ID_PRO: str = ""
    STRIPE_PRICE_ID_BUSINESS: str = ""

    # ── OAuth – Slack ─────────────────────────────────────────────────
    SLACK_CLIENT_ID: str = ""
    SLACK_CLIENT_SECRET: str = ""
    SLACK_SIGNING_SECRET: str = ""

    # ── OAuth – GitHub ────────────────────────────────────────────────
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    # ── OAuth – Notion ────────────────────────────────────────────────
    NOTION_CLIENT_ID: str = ""
    NOTION_CLIENT_SECRET: str = ""

    # ── OAuth – Discord ───────────────────────────────────────────────
    DISCORD_CLIENT_ID: str = ""
    DISCORD_CLIENT_SECRET: str = ""

    # ── OAuth – HubSpot ───────────────────────────────────────────────
    HUBSPOT_CLIENT_ID: str = ""
    HUBSPOT_CLIENT_SECRET: str = ""

    # ── OAuth – Airtable ──────────────────────────────────────────────
    AIRTABLE_CLIENT_ID: str = ""
    AIRTABLE_CLIENT_SECRET: str = ""

    # ── WhatsApp (Meta Cloud API – operator registers app once) ───────
    WHATSAPP_APP_ID: str = ""
    WHATSAPP_APP_SECRET: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "autoflow_whatsapp_verify"

    # ── Telegram (bot token – operator creates bot via @BotFather) ────
    TELEGRAM_BOT_TOKEN: str = ""

    # ── SMTP fallback ─────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""

    # ── AI / LLM nodes ───────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    # Extended LLM providers
    GOOGLE_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    HUGGINGFACE_API_KEY: str = ""
    COHERE_API_KEY: str = ""
    MISTRAL_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    TOGETHER_API_KEY: str = ""
    PERPLEXITY_API_KEY: str = ""
    REPLICATE_API_KEY: str = ""
    # Azure OpenAI
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o"
    # Tool nodes
    BRAVE_SEARCH_API_KEY: str = ""
    SERPAPI_API_KEY: str = ""
    OPENWEATHERMAP_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    EXA_API_KEY: str = ""
    E2B_API_KEY: str = ""
    # AWS (shared for S3, SNS, DynamoDB)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    # Document loaders / integrations
    NOTION_API_KEY: str = ""
    GITHUB_TOKEN: str = ""
    # New SaaS integrations
    ZENDESK_SUBDOMAIN: str = ""
    ZENDESK_EMAIL: str = ""
    ZENDESK_API_TOKEN: str = ""
    LINEAR_API_KEY: str = ""
    SALESFORCE_CLIENT_ID: str = ""
    SALESFORCE_CLIENT_SECRET: str = ""
    SALESFORCE_USERNAME: str = ""
    SALESFORCE_PASSWORD: str = ""
    SALESFORCE_SECURITY_TOKEN: str = ""
    CONFLUENCE_BASE_URL: str = ""
    CONFLUENCE_EMAIL: str = ""
    CONFLUENCE_API_TOKEN: str = ""
    ZOOM_ACCOUNT_ID: str = ""
    ZOOM_CLIENT_ID: str = ""
    ZOOM_CLIENT_SECRET: str = ""
    MONDAY_API_KEY: str = ""
    MAILCHIMP_API_KEY: str = ""
    MAILCHIMP_SERVER: str = "us1"
    FRESHDESK_DOMAIN: str = ""
    FRESHDESK_API_KEY: str = ""
    INTERCOM_ACCESS_TOKEN: str = ""
    TYPEFORM_ACCESS_TOKEN: str = ""
    BOX_ACCESS_TOKEN: str = ""
    BOX_CLIENT_ID: str = ""
    BOX_CLIENT_SECRET: str = ""
    BOX_ENTERPRISE_ID: str = ""
    DROPBOX_ACCESS_TOKEN: str = ""

    # ── Extended LLM providers ────────────────────────────────────────
    OPENROUTER_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    XAI_API_KEY: str = ""
    FIREWORKS_API_KEY: str = ""
    CEREBRAS_API_KEY: str = ""
    SAMBANOVA_API_KEY: str = ""
    LOCAL_AI_BASE_URL: str = "http://localhost:8080"
    LOCAL_AI_API_KEY: str = ""
    LITELLM_BASE_URL: str = "http://localhost:4000"
    LITELLM_API_KEY: str = ""

    # ── Embedding providers ───────────────────────────────────────────
    JINA_API_KEY: str = ""
    VOYAGE_API_KEY: str = ""
    NOMIC_API_KEY: str = ""

    # ── Vector stores ─────────────────────────────────────────────────
    PINECONE_API_KEY: str = ""
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    WEAVIATE_URL: str = "http://localhost:8080"
    WEAVIATE_API_KEY: str = ""
    CHROMA_URL: str = "http://localhost:8000"
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    ELASTICSEARCH_API_KEY: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    UPSTASH_VECTOR_REST_URL: str = ""
    UPSTASH_VECTOR_REST_TOKEN: str = ""
    MONGODB_URL: str = "mongodb://localhost:27017"
    MILVUS_URL: str = "http://localhost:19530"
    MILVUS_TOKEN: str = ""
    OPENSEARCH_URL: str = "http://localhost:9200"
    OPENSEARCH_PASSWORD: str = ""

    # ── Graph databases ───────────────────────────────────────────────
    NEO4J_URL: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""

    # ── Cache / Memory backends ───────────────────────────────────────
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""
    MOMENTO_API_KEY: str = ""
    ZEP_URL: str = "http://localhost:8000"
    ZEP_API_KEY: str = ""
    SQLITE_PATH: str = "/tmp/autoflow_records.db"
    MYSQL_URL: str = "mysql+pymysql://root:@localhost/autoflow"

    # ── Analytics / Observability ─────────────────────────────────────
    LANGSMITH_API_KEY: str = ""
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    LANGWATCH_API_KEY: str = ""
    ARIZE_API_KEY: str = ""
    ARIZE_SPACE_ID: str = ""
    ARIZE_PHOENIX_ENDPOINT: str = "http://localhost:6006/v1/traces"
    LUNARY_APP_ID: str = ""
    OPIK_API_KEY: str = ""

    # ── Speech-to-text ────────────────────────────────────────────────
    ASSEMBLYAI_API_KEY: str = ""

    # ── Tool nodes ────────────────────────────────────────────────────
    WOLFRAM_ALPHA_APP_ID: str = ""
    GOOGLE_CSE_API_KEY: str = ""
    GOOGLE_CSE_ID: str = ""
    SERPER_API_KEY: str = ""
    SEARXNG_BASE_URL: str = ""

    # ── Document loaders ──────────────────────────────────────────────
    FIRECRAWL_API_KEY: str = ""
    GITBOOK_API_TOKEN: str = ""
    GOOGLE_ACCESS_TOKEN: str = ""
    JIRA_BASE_URL: str = ""
    JIRA_EMAIL: str = ""
    JIRA_API_TOKEN: str = ""

    # ── Monitoring ────────────────────────────────────────────────────
    PROMETHEUS_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"
    OTEL_ENABLED: bool = True
    OTEL_EXPORTER_ENDPOINT: str = "http://otel-collector:4318"

    # ── Derived helpers ───────────────────────────────────────────────
    @property
    def oauth_redirect_base(self) -> str:
        return f"{self.APP_BASE_URL}/oauth/callback"

    @property
    def frontend_url(self) -> str:
        return self.FRONTEND_URL or self.APP_BASE_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()