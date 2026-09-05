"""Twenty CRM integration — people and companies via GraphQL."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("twenty.list_people")
async def twenty_list_people(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List people from Twenty CRM via GraphQL.

    config/input_data:
      api_key  — Twenty API key (required)
      base_url — base URL of the Twenty instance, e.g. https://api.twenty.com (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    base_url = (merged.get("base_url") or "").rstrip("/")

    if not base_url:
        raise ValueError("base_url is required for twenty.list_people")

    headers = {"Authorization": f"Bearer {api_key}"}
    query = """
    query {
      people {
        edges {
          node {
            id
            name {
              firstName
              lastName
            }
            emails {
              primaryEmail
            }
            createdAt
          }
        }
      }
    }
    """

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/graphql", headers=headers, json={"query": query})
        r.raise_for_status()
        data = r.json()

    people = [edge["node"] for edge in data.get("data", {}).get("people", {}).get("edges", [])]
    log.info("twenty.list_people", count=len(people))
    return {"people": people, "count": len(people)}


@register_node("twenty.create_person")
async def twenty_create_person(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new person in Twenty CRM via GraphQL mutation.

    config/input_data:
      api_key    — Twenty API key (required)
      base_url   — base URL of the Twenty instance (required)
      first_name — first name (required)
      last_name  — last name
      email      — primary email address
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    base_url = (merged.get("base_url") or "").rstrip("/")
    fn = merged.get("first_name") or ""
    ln = merged.get("last_name") or ""
    email = merged.get("email") or ""

    if not base_url:
        raise ValueError("base_url is required for twenty.create_person")
    if not fn:
        raise ValueError("first_name is required for twenty.create_person")

    headers = {"Authorization": f"Bearer {api_key}"}
    mutation = """
    mutation CreatePerson($firstName: String!, $lastName: String, $email: String) {
      createPerson(data: {
        name: { firstName: $firstName, lastName: $lastName }
        emails: { primaryEmail: $email }
      }) {
        id
        name {
          firstName
          lastName
        }
        emails {
          primaryEmail
        }
        createdAt
      }
    }
    """
    variables = {"firstName": fn, "lastName": ln, "email": email}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{base_url}/graphql",
            headers=headers,
            json={"query": mutation, "variables": variables},
        )
        r.raise_for_status()
        data = r.json()

    person = data.get("data", {}).get("createPerson", data)
    log.info("twenty.create_person", first_name=fn, last_name=ln)
    return {"person": person}


@register_node("twenty.list_companies")
async def twenty_list_companies(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List companies from Twenty CRM via GraphQL.

    config/input_data:
      api_key  — Twenty API key (required)
      base_url — base URL of the Twenty instance (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    base_url = (merged.get("base_url") or "").rstrip("/")

    if not base_url:
        raise ValueError("base_url is required for twenty.list_companies")

    headers = {"Authorization": f"Bearer {api_key}"}
    query = """
    query {
      companies {
        edges {
          node {
            id
            name
            domainName {
              primaryLinkUrl
            }
            createdAt
          }
        }
      }
    }
    """

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/graphql", headers=headers, json={"query": query})
        r.raise_for_status()
        data = r.json()

    companies = [edge["node"] for edge in data.get("data", {}).get("companies", {}).get("edges", [])]
    log.info("twenty.list_companies", count=len(companies))
    return {"companies": companies, "count": len(companies)}
