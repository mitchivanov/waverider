class NotificationManager:
    _instance = None
    _broadcast_callback = None

    @classmethod
    def initialize(cls, broadcast_callback):
        cls._broadcast_callback = broadcast_callback

    @classmethod
    async def send_notification(cls, notification_type: str, bot_id: int, data: dict):
        if cls._broadcast_callback:
            await cls._broadcast_callback({
                "type": "notification",
                "notification_type": notification_type,
                "bot_id": bot_id,
                "payload": data
            }) 