"""Your data: where it is, backups, restore, export, delete."""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from src import data_admin

router = APIRouter(prefix="/api/data", tags=["data"])


class DeleteIn(BaseModel):
    confirm: str
    include_backups: bool = False


@router.get("/summary")
def summary():
    return data_admin.summary()


@router.get("/backups")
def backups():
    return data_admin.list_backups()


@router.post("/backups")
def backup_now():
    return data_admin.create_backup("manual")


@router.post("/backups/{name}/restore")
def restore(name: str):
    try:
        return data_admin.restore_backup(name)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _download(content: bytes, media_type: str, ext: str) -> Response:
    name = f"KaisenOS-export-{datetime.now():%Y%m%d-%H%M}.{ext}"
    return Response(
        content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )


@router.get("/export.json")
def export_json():
    return _download(data_admin.export_json_bytes(), "application/json", "json")


@router.get("/export.zip")
def export_csv():
    return _download(data_admin.export_csv_zip_bytes(), "application/zip", "zip")


@router.post("/delete")
def delete_everything(body: DeleteIn):
    if body.confirm != "DELETE":
        raise HTTPException(status_code=422, detail='Type DELETE to confirm.')
    return data_admin.delete_all_data(include_backups=body.include_backups)
