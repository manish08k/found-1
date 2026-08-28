"""Google Drive integration — upload, download, list, move, share, polling."""
import io
import structlog
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials

from core.execution_engine import register_node
from triggers.engine import register_poller
from credentials.encryption import decrypt_credential
from core.config import settings

log = structlog.get_logger(__name__)


async def _drive_service(credential_id: str, db):
    from sqlalchemy import select
    from storage.models import OAuthCredential
    result = await db.execute(select(OAuthCredential).where(OAuthCredential.id == credential_id))
    cred_row = result.scalar_one()
    token_data = decrypt_credential(cred_row.encrypted_token, settings.CREDENTIAL_ENCRYPTION_KEY)
    creds = Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


@register_node("drive.list_files")
async def drive_list_files(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _drive_service(credential_id, db)
    query = config.get("query") or input_data.get("query", "")
    folder_id = config.get("folder_id") or input_data.get("folder_id")
    page_size = config.get("page_size", 50)

    q_parts = []
    if folder_id:
        q_parts.append(f"'{folder_id}' in parents")
    if query:
        q_parts.append(query)
    q_parts.append("trashed = false")

    result = service.files().list(
        q=" and ".join(q_parts),
        pageSize=page_size,
        fields="files(id, name, mimeType, size, modifiedTime, webViewLink, parents)",
    ).execute()
    return {"files": result.get("files", [])}


@register_node("drive.upload_file")
async def drive_upload_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _drive_service(credential_id, db)
    name = config.get("name") or input_data.get("name", "upload.txt")
    content = config.get("content") or input_data.get("content", "")
    mime_type = config.get("mime_type", "text/plain")
    folder_id = config.get("folder_id") or input_data.get("folder_id")

    if isinstance(content, str):
        content = content.encode()

    metadata = {"name": name}
    if folder_id:
        metadata["parents"] = [folder_id]

    media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type)
    result = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, name, webViewLink",
    ).execute()
    return {"file_id": result["id"], "name": result["name"], "url": result.get("webViewLink")}


@register_node("drive.download_file")
async def drive_download_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _drive_service(credential_id, db)
    file_id = config.get("file_id") or input_data.get("file_id")

    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    import base64
    content_b64 = base64.b64encode(buf.getvalue()).decode()
    return {"file_id": file_id, "content_base64": content_b64}


@register_node("drive.create_folder")
async def drive_create_folder(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _drive_service(credential_id, db)
    name = config.get("name") or input_data.get("name")
    parent_id = config.get("parent_id") or input_data.get("parent_id")

    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    result = service.files().create(body=metadata, fields="id, name").execute()
    return {"folder_id": result["id"], "name": result["name"]}


@register_node("drive.move_file")
async def drive_move_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _drive_service(credential_id, db)
    file_id = config.get("file_id") or input_data.get("file_id")
    new_folder_id = config.get("folder_id") or input_data.get("folder_id")

    file = service.files().get(fileId=file_id, fields="parents").execute()
    previous_parents = ",".join(file.get("parents", []))

    result = service.files().update(
        fileId=file_id,
        addParents=new_folder_id,
        removeParents=previous_parents,
        fields="id, parents",
    ).execute()
    return {"file_id": result["id"]}


@register_node("drive.share_file")
async def drive_share_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _drive_service(credential_id, db)
    file_id = config.get("file_id") or input_data.get("file_id")
    email = config.get("email") or input_data.get("email")
    role = config.get("role", "reader")  # reader, writer, commenter

    permission = {"type": "user", "role": role, "emailAddress": email}
    result = service.permissions().create(
        fileId=file_id,
        body=permission,
        fields="id",
    ).execute()
    return {"permission_id": result["id"], "file_id": file_id}


@register_node("drive.delete_file")
async def drive_delete_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _drive_service(credential_id, db)
    file_id = config.get("file_id") or input_data.get("file_id")
    service.files().delete(fileId=file_id).execute()
    return {"ok": True, "file_id": file_id}


# ─── Polling: new file in folder ─────────────────────────────────────────────

_drive_seen: dict[str, set] = {}


@register_poller("drive", "new_file")
async def poll_drive_new_file(config: dict, credential_id: str, db) -> list[dict]:
    service = await _drive_service(credential_id, db)
    folder_id = config.get("folder_id")
    key = f"{credential_id}:{folder_id}"

    if key not in _drive_seen:
        _drive_seen[key] = set()

    try:
        q = f"'{folder_id}' in parents and trashed = false" if folder_id else "trashed = false"
        result = service.files().list(
            q=q,
            pageSize=20,
            orderBy="createdTime desc",
            fields="files(id, name, mimeType, size, webViewLink, createdTime)",
        ).execute()

        new_items = []
        for f in result.get("files", []):
            if f["id"] not in _drive_seen[key]:
                new_items.append(f)
                _drive_seen[key].add(f["id"])

        return new_items
    except Exception as e:
        log.error("drive_poll_error", error=str(e))
        return []
