"""Abstract port for sending messages back to the user on their channel."""

from abc import ABC, abstractmethod


class OutboundChannelPort(ABC):
    channel_name: str

    @abstractmethod
    async def send_text(self, to: str, text: str) -> None:
        ...
