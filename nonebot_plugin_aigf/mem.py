from dataclasses import dataclass
from datetime import datetime


@dataclass
class Message:
    time: datetime
    user_name: str
    content: str
    user_id: str = ""
