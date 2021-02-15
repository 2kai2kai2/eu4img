from aiohttp_requests import requests

async def upload(file, name: str, key: str) -> str:
    files = {name: file}
    try:
        r = await requests.post(f"https://skanderbeg.pm/api.php?key={key}&scope=uploadSaveFile", data=files)
    except Exception as e:
        print("Upload to Skanderbeg failed.")
        print(repr(e))
        return None
    if r.status == 200:
        json = await r.json()
        if json is not None and json["success"]:
            return f"https://skanderbeg.pm/browse.php?id={json['hash']}"
    return None