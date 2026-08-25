from dataclasses import dataclass
from typing import Optional


@dataclass
class Upload:
    id: str
    server_id: str
    uploaded_by: str
    username: str
    type: str
    name: str
    status: str = "ok"
    error: Optional[str] = None
    uploaded_at: Optional[str] = None
    content_id: Optional[str] = None
    feed_id: Optional[str] = None
    deleted_at: Optional[str] = None
