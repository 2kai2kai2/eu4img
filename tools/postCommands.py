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
            "type": 5,  # BOOLEAN
            "name": "skanderbeg",
            "description": "Specify whether to upload to skanderbeg.pm (default: False)",
            "required": False
        }
    ]
})
uploadCommand({
    "name": "defaultban",
    "description": "Modifies the default ban list for nation reservations.",
    "options": [
        {
            "type": 1,  # SUB_COMMAND
            "name": "add",
            "description": "Add a tag to the default ban list.",
            "options": [
                {
                    "type": 3,  # STRING
                    "name": "tag",
                    "description": "The name of the country to add to the ban list.",
                    "required": True
                }
            ]
        }, {
            "type": 1,  # SUB_COMMAND
            "name": "del",
            "description": "Remove a tag from the default ban list.",
            "options": [
                {
                    "type": 3,  # STRING
                    "name": "tag",
                    "description": "The name of the country to remove from the ban list.",
                    "required": True
                }
            ]
        }, {
            "type": 1,  # SUB_COMMAND
            "name": "list",
            "description": "Returns all nations currently on the default ban list."
        }
    ]
})
uploadCommand({
    "name": "adminrank",
    "description": "Sets the role required to have bot admin permissions. All higher roles will have permission.",
    "options": [
        {
            "type": 8,  # ROLE
            "name": "role",
            "description": "The new minimum admin role.",
            "required": True
        }
    ]
})
