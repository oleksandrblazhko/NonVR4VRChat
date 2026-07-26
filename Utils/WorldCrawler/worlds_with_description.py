"""
world_descriptions.py

Для кожного світу із вхідного JSON отримує поле description
через GET /worlds/{worldId} та додає його у вихідний JSON.

Запуск:

    python world_descriptions.py worlds.json worlds_with_description.json
"""

import json
import sys
import time
from pathlib import Path

import requests

from config import USERNAME, PASSWORD, USER_AGENT

API = "https://api.vrchat.cloud/api/1"

REQUEST_TIMEOUT = 30
RETRY_DELAY = 10


class VRChatClient:

    def __init__(self):

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": USER_AGENT
        })

    # ---------------------------------------------------------

    def login(self):

        print("Login...")

        response = self.session.get(
            f"{API}/auth/user",
            auth=(USERNAME, PASSWORD),
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        #
        # Two Factor Authentication
        #

        if "requiresTwoFactorAuth" in data:

            methods = data["requiresTwoFactorAuth"]

            if "emailOtp" not in methods:
                raise RuntimeError(
                    f"Unsupported 2FA method: {methods}"
                )

            print()
            print("Email verification required.")

            while True:

                code = input("Email code: ").strip()

                verify = self.session.post(
                    f"{API}/auth/twofactorauth/emailotp/verify",
                    json={"code": code},
                    timeout=REQUEST_TIMEOUT,
                )

                if verify.status_code != 200:
                    print("Incorrect code.")
                    continue

                result = verify.json()

                if result.get("verified", False):
                    break

        print("Login successful.")

    # ---------------------------------------------------------

    def get_world(self, world_id):

        """
        Повертає повний JSON світу.
        Автоматично повторює запит при HTTP 429.
        """

        while True:

            response = self.session.get(
                f"{API}/worlds/{world_id}",
                timeout=REQUEST_TIMEOUT,
            )

            #
            # Too Many Requests
            #

            if response.status_code == 429:

                print("HTTP 429. Waiting...")

                time.sleep(RETRY_DELAY)

                continue

            response.raise_for_status()

            return response.json()
        
        # ---------------------------------------------------------

def save_output(filename, worlds):

    with open(filename, "w", encoding="utf-8") as fp:

        json.dump(
            worlds,
            fp,
            indent=4,
            ensure_ascii=False,
        )


# ---------------------------------------------------------

def main():

    if len(sys.argv) != 3:

        print()
        print("Usage:")
        print("    python world_descriptions.py input.json output.json")
        return

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])

    #
    # Read input
    #

    with open(input_file, "r", encoding="utf-8") as fp:

        worlds = json.load(fp)

    total = len(worlds)

    print()
    print(f"Worlds: {total}")
    print()

    #
    # Login
    #

    client = VRChatClient()

    client.login()

    print()

    #
    # Process worlds
    #

    for index, world in enumerate(worlds, start=1):

        world_id = world.get("id", "")

        name = world.get("name", "")

        print(f"[{index}/{total}] {world_id}  {name}")

        try:

            data = client.get_world(world_id)

            #
            # Copy description
            #

            world["description"] = data.get("description")

            if world["description"] is None:

                print("    description: <None>")

            else:

                text = world["description"].replace("\n", " ")

                if len(text) > 80:
                    text = text[:80] + "..."

                print(f"    description: {text}")

        except Exception as ex:

            print(f"    ERROR: {ex}")

            world["description"] = None

        #
        # Save after every world
        #

        save_output(output_file, worlds)

    print()
    print("Finished.")
    print(f"Saved to: {output_file}")


# ---------------------------------------------------------

if __name__ == "__main__":
    main()