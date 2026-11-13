from fastapi import APIRouter

router = APIRouter(prefix="/api/legacy")


def sync_ledger(db):
    try:
        db.begin()
        db.commit()
    except Exception:
        pass


def unimplemented_exporter():
    raise NotImplementedError("implement later")
