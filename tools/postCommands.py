from typing import Any, Dict

import requests

appID = input("Application ID: ")
token = input("Token: ")

authheader = {
    "Authorization": f"Bot {token}"
}


def uploadCommand(cmdjson: Dict[str, Any]):
    r = requests.post(
        f"https://discord.com/api/v8/applications/{appID}/commands", headers=authheader, json=cmdjson)
    print(r.json())


uploadCommand({
    "name": "reservations",
    "description": "Creates a new Cartographer reservation channel."
})
uploadCommand({
    "name": "asireservations",
    "description": "Creates a new Cartographer ASI reservation channel."
})
uploadCommand({
    "name": "stats",
    "description": "Creates a Cartographer stats display.",
    "options": [
        {
            "name": "skanderbeg",
            "description": "Specify whether to upload to skanderbeg.pm (default: False)",
            "type": 5,
            "required": False
        }
    ]
})
