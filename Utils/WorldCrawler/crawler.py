"""
crawler.py

Перша версія завантажувача світів VRChat.

Функції

    • авторизація
    • посторінкове завантаження
    • автоматичні повторні спроби
    • пауза між запитами
    • збереження сирого JSON
"""
import os

from pathlib import Path
import json
import time

import requests

from config import *


API = "https://api.vrchat.cloud/api/1"


class WorldCrawler:

    def __init__(self):

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": USER_AGENT
        })

        Path(OUTPUT_DIR).mkdir(exist_ok=True)

    # ----------------------------------------------------------

    def login(self):

        print("Login...")

        response = self.session.get(
            f"{API}/auth/user",
            auth=(USERNAME, PASSWORD),
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        # -------------------------------------------------
        # Двофакторна автентифікація
        # -------------------------------------------------

        if "requiresTwoFactorAuth" in data:

            methods = data["requiresTwoFactorAuth"]

            if "emailOtp" not in methods:
                raise RuntimeError(
                    f"Unsupported 2FA method: {methods}"
                )

            print()
            print("===================================================")
            print(" Email verification required")
            print("===================================================")
            print("A one-time verification code has been sent")
            print("to your email address.")
            print()

            verified = False

            for attempt in range(1, 4):

                code = input(
                    f"Enter email code (attempt {attempt}/3): "
                ).strip()

                verify = self.session.post(
                    f"{API}/auth/twofactorauth/emailotp/verify",
                    json={"code": code},
                    timeout=30,
                )

                if verify.status_code != 200:

                    print("Incorrect code.")
                    print()

                    continue

                result = verify.json()

                if result.get("verified", False):

                    verified = True

                    print()
                    print("✓ Email verification successful.")
                    break

                print("Verification failed.")
                print()

            if not verified:

                raise RuntimeError(
                    "Unable to verify email code."
                )

            # -------------------------------------------------
            # Перевірка авторизованої сесії
            # -------------------------------------------------

            print()
            print("Checking authenticated session...")

            response = self.session.get(
                f"{API}/auth/user",
                timeout=30,
            )

            response.raise_for_status()

            profile = response.json()

            if "requiresTwoFactorAuth" in profile:

                raise RuntimeError(
                    "2FA verification was not completed."
                )

            print("Authenticated as:")
            print(f"  Display name : {profile.get('displayName')}")
            print(f"  User ID      : {profile.get('id')}")
            print()

        print("Login OK")

    # ----------------------------------------------------------

    def load_page(self, offset):

        params = {
            "n": PAGE_SIZE,
            "offset": offset,            
            "sort": "favorites",
            "tag": "author_tag_game",
            "tag": "author_tag_puzzle",
        }

        retry_delay = RETRY_DELAY

        for attempt in range(1, MAX_RETRIES + 1):

            print(f"Loading offset={offset} (try {attempt})")

            try:

                response = self.session.get(
                    f"{API}/worlds",
                    params=params,
                    timeout=30,
                )

                # --------------------------------------------------
                # 429 Too Many Requests
                # --------------------------------------------------

                if response.status_code == 429:

                    retry_after = response.headers.get("Retry-After")

                    if retry_after:
                        wait = float(retry_after)
                    else:
                        wait = retry_delay
                        retry_delay *= 2

                    print(f"Rate limit. Waiting {wait:.1f} sec.")
                    time.sleep(wait)
                    continue

                # --------------------------------------------------
                # 403 Forbidden
                # --------------------------------------------------

                if response.status_code == 403:

                    print()
                    print("=" * 70)
                    print("HTTP 403 FORBIDDEN")
                    print("=" * 70)
                    print("URL:")
                    print(response.request.url)
                    print()

                    print("Headers:")
                    for k, v in response.headers.items():
                        print(f"{k}: {v}")

                    print()

                    print("Response:")

                    try:
                        print(
                            json.dumps(
                                response.json(),
                                indent=2,
                                ensure_ascii=False,
                            )
                        )
                    except Exception:
                        print(response.text)

                    raise RuntimeError(
                        f"API rejected request (offset={offset})."
                    )

                # --------------------------------------------------
                # Інші HTTP-помилки
                # --------------------------------------------------

                if not response.ok:

                    print()
                    print("=" * 70)
                    print("HTTP ERROR")
                    print("=" * 70)
                    print("Status :", response.status_code)
                    print("URL    :", response.request.url)
                    print()

                    print("Headers:")
                    for k, v in response.headers.items():
                        print(f"{k}: {v}")

                    print()

                    print("Response:")

                    try:
                        print(
                            json.dumps(
                                response.json(),
                                indent=2,
                                ensure_ascii=False,
                            )
                        )
                    except Exception:
                        print(response.text)

                    response.raise_for_status()

                # --------------------------------------------------
                # Успішний запит
                # --------------------------------------------------

                data = response.json()

                time.sleep(REQUEST_DELAY)

                return data

            except requests.ConnectionError as ex:

                print(f"Connection error: {ex}")

            except requests.Timeout as ex:

                print(f"Timeout: {ex}")

            except requests.RequestException as ex:

                print(f"Request error: {ex}")

            # ------------------------------------------------------
            # Повторна спроба лише для мережевих помилок
            # ------------------------------------------------------

            if attempt == MAX_RETRIES:
                raise

            print(f"Retry after {retry_delay:.1f} sec.")

            time.sleep(retry_delay)

            retry_delay *= 2

        raise RuntimeError("Unable to load page")

    # ----------------------------------------------------------

    def crawl(self):

        # page = 1
        # offset = 0
        page, offset = self.load_checkpoint()

        while True:

            worlds = self.load_page(offset)

            if not worlds:

                print()
                print("Finished.")
                break

            self.save_page(page, worlds)

            self.save_checkpoint(
                page + 1,
                offset + PAGE_SIZE,
            )

            print(
                f"Page {page:4d} | "
                f"Offset {offset:6d} | "
                f"Worlds {len(worlds)}"
            )

            page += 1
            offset += PAGE_SIZE

    # ----------------------------------------------------------

    def checkpoint_file(self):

        return Path(OUTPUT_DIR) / "checkpoint.json"

    # ----------------------------------------------------------

    def load_checkpoint(self):

        checkpoint = self.checkpoint_file()

        #
        # 1. Використовуємо checkpoint
        #

        if checkpoint.exists():

            with open(checkpoint, "r", encoding="utf-8") as fp:

                data = json.load(fp)

            print(
                f"Resume from checkpoint "
                f"(page={data['page']}, offset={data['offset']})"
            )

            return data["page"], data["offset"]

        #
        # 2. Якщо checkpoint відсутній —
        #    шукаємо останній page_XXXX.json
        #

        files = sorted(Path(OUTPUT_DIR).glob("page_*.json"))

        if not files:

            print("Start from beginning.")

            return 1, 0

        last = files[-1]

        page = int(last.stem.split("_")[1])

        offset = page * PAGE_SIZE

        print(
            f"Resume from existing files "
            f"(page={page+1}, offset={offset})"
        )

        return page + 1, offset

    # ----------------------------------------------------------

    def save_checkpoint(self, page, offset):

        with open(
            self.checkpoint_file(),
            "w",
            encoding="utf-8",
        ) as fp:

            json.dump(
                {
                    "page": page,
                    "offset": offset,
                },
                fp,
                indent=2,
            )

    # ----------------------------------------------------------

    def save_page(self, page_number, data):

        filename = Path(OUTPUT_DIR) / f"page_{page_number:04d}.json"

        with open(filename, "w", encoding="utf-8") as fp:

            json.dump(
                data,
                fp,
                indent=2,
                ensure_ascii=False,
            )

        print(f"Saved: {filename}")