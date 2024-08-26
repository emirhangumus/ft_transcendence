def genResponse(status: bool, message: str, data: dict | None) -> dict:
    if status:
        return {
            "status": True,
            "message": message,
            "data": data
        }
    else:
        return {
            "status": False,
            "message": message,
            "data": None
        }