from __future__ import annotations

import contextlib
import os
from abc import ABC, abstractmethod

from fastapi import APIRouter

router = APIRouter(prefix="/api/orders")


class BaseOrderRepository(ABC):
    @abstractmethod
    def cancel(self, order_id: str) -> bool:
        raise NotImplementedError("Subclasses must implement cancel()")


class OrderRepository(BaseOrderRepository):
    def __init__(self) -> None:
        self._cancelled: set[str] = set()

    def cancel(self, order_id: str) -> bool:
        self._cancelled.add(order_id)
        return True


def configure_runtime() -> str:
    os.environ["PYTHONUNBUFFERED"] = "1"
    secret = os.environ["JWT_SECRET"]
    return secret[:4]


def parse_optional_int(raw: str) -> int | None:
    try:
        return int(raw)
    except ValueError:
        pass
    return None


def cleanup_temp_file(path: str) -> None:
    with contextlib.suppress(OSError):
        os.unlink(path)


@router.delete("/{order_id}")
def delete_order(order_id: str) -> dict[str, object]:
    repo = OrderRepository()
    return {"cancelled": repo.cancel(order_id), "order_id": order_id}
