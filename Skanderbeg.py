import aiohttp


async def upload(file: bytes, name: str, key: str) -> str:
    files = aiohttp.FormData()
    files.add_field("file", file, filename=name, content_type="multipart/form-data")
    try:
        session = aiohttp.ClientSession()
        r = await session.post(f"https://skanderbeg.pm/api.php?key={key}&scope=uploadSaveFile", data=files)
        await session.connector.close()
        await session.close()
    except Exception as e:
        print("Upload to Skanderbeg failed.")
        print(repr(e))
        return None
    if r.status == 200:
        json: dict = await r.json()
        if json is not None and json["success"]:
            r.close()
            return f"https://skanderbeg.pm/browse.php?id={json['hash']}"
        elif json is None:
            return f"```Skanderbeg upload failed due to lack of response data.\n{await r.content.read()}```"
        else:
            return f"```Skanderbeg upload failed.\n{json}```"
    else:
        return f"```Skanderbeg upload failed with code {r.status}.```"
