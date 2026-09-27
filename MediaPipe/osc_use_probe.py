"""
osc_use_probe.py

Ручна перевірка кнопок VRChat через OSC: `/input/UseRight`,
`/input/GrabRight`, `/input/DropRight` тощо.

Камера і MediaPipe не потрібні - програма лише шле повідомлення з
терміналу, щоб визначити, чи взагалі спрацьовує команда і з якою
семантикою (клік чи утримування).

    python osc_use_probe.py                       # 5 коротких натискань UseRight
    python osc_use_probe.py --hold 3              # тримати UseRight=1 три секунди
    python osc_use_probe.py --address GrabRight   # порівняти з хапком
    python osc_use_probe.py --count 0             # нескінченно, до Ctrl+C
    python osc_use_probe.py --dry-run             # нічого не надсилати

Дві умови, без яких тест нічого не покаже:

    1. Вікно VRChat має бути сфокусованим у момент надсилання - без фокусу
       кнопки рук у десктопі не працюють.
    2. Use і Grab діють на предмет, ПІДСВІЧЕНИЙ вказаною рукою, а Drop - на
       той, що вже У РУЦІ. Тримай предмет у правій руці або наведи праву
       руку на предмет, інакше реакції не буде навіть якщо команда доходить.

Якщо запущений main.py, вимкни його: він паралельно шле свої команди й
перекриває результат.
"""

from __future__ import annotations

import argparse
import sys
import time

from osc_sender import OSCSender


# ============================================================
# Parameters
# ============================================================

# Кнопки з офіційного списку /input/, які має сенс перевіряти.
BUTTONS = (
    "UseRight",
    "UseLeft",
    "GrabRight",
    "GrabLeft",
    "DropRight",
    "DropLeft",
)


# ============================================================
# Sending
# ============================================================

def resolve_address(name: str) -> str:
    """
    `UseRight` -> `/input/UseRight`; готову адресу лишає як є.

    Git Bash ламає аргументи, що починаються з `/`: MSYS перетворює
    `/input/Jump` на `C:/Program Files/Git/input/Jump`. Тому якщо `/input/`
    трапляється в рядку будь-де, беремо те, що після останнього входження.
    Простіше - передавай голу назву: `--address UseRight`.
    """

    marker = "/input/"

    if name.startswith("input/"):

        name = "/" + name

    if marker in name:

        tail = name.rsplit(marker, 1)[1]

        return marker + tail if tail else name

    if name.startswith("/"):

        return name

    return marker + name


def send(sender: OSCSender, address: str, value, dry_run: bool):

    print(f"   {'[dry-run]' if dry_run else '->'} {address} = {value}")

    if not dry_run:

        sender.client.send_message(address, value)


def press_cycle(sender, address, hold_seconds, as_int, dry_run):
    """
    Натискання: 1, утримати hold_seconds, відпустити в 0.
    """

    send(sender, address, 1 if as_int else True, dry_run)

    time.sleep(hold_seconds)

    send(sender, address, 0 if as_int else False, dry_run)


def hint_for(short: str) -> str:
    """
    Що тримати в руці під час цього тесту.
    """

    if short.startswith("Drop"):

        return "у руці має ЩЕ ЩОСЬ БУТИ (Drop кидає те, що вже тримаєш)"

    if short.startswith("Use"):

        return "наведи цю руку на предмет (Use діє на підсвічений предмет)"

    return "наведи цю руку на предмет (Grab діє на підсвічений предмет)"


# ============================================================
# Main
# ============================================================

def build_parser():

    parser = argparse.ArgumentParser(
        description="Перевірка кнопок /input/ у VRChat через OSC.",
        epilog="Приклад:  python osc_use_probe.py --hold 3 --count 2 --start-delay 8",
    )

    parser.add_argument(
        "--address",
        default="UseRight",
        help="кнопка з "
        + ", ".join(BUTTONS)
        + " (у Git Bash краще гола назва: UseRight) або повна адреса /input/UseRight",
    )

    parser.add_argument(
        "--hold",
        type=float,
        default=0.1,
        help="скільки секунд тримати 1 перед 0 (0.1 = короткий клік, 3 = утримування)",
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=3.0,
        help="пауза між циклами, секунд",
    )

    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="кількість циклів; 0 - нескінченно до Ctrl+C",
    )

    parser.add_argument(
        "--start-delay",
        type=float,
        default=8.0,
        help="зворотний відлік на старті, щоб встигнути перевести фокус у VRChat",
    )

    parser.add_argument(
        "--as-int",
        action="store_true",
        help='надсилати 1/0 цілими замість True/False (документація каже "int of 1")',
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="нічого не надсилати, лише показати, що б надіслалось",
    )

    return parser


def countdown(seconds: float, hint: str):

    if seconds <= 0:

        return

    print(f"Переведи фокус у VRChat - є {seconds:.0f} с, {hint}:")

    remaining = int(seconds)

    while remaining > 0:

        print(f"  {remaining}...")

        time.sleep(1)

        remaining -= 1


def main(argv=None) -> int:

    args = build_parser().parse_args(argv)

    address = resolve_address(args.address)

    short = address.rsplit("/", 1)[-1]

    sender = OSCSender()

    print("------------------------------------")
    print(f"Адреса      : {address}")
    print(f"Значення    : {'1/0' if args.as_int else 'True/False'}")
    print(f"Куди        : {sender.ip}:{sender.port}")
    print(f"Тривалість  : {args.hold} с   інтервал: {args.interval} с   циклів: {args.count or 'безліч'}")
    print(f"Режим       : {'dry-run (нічого не летить)' if args.dry_run else 'надсилання'}")
    print(f"Підказка    : {hint_for(short)}")

    if short not in BUTTONS:

        print(f"Увага       : '{short}' немає серед відомих кнопок - надсилаю як є.")

    print("------------------------------------")

    try:

        countdown(args.start_delay, hint_for(short))

        cycle = 0

        while True:

            cycle += 1

            print(f"Цикл {cycle}: натискаю {short}")

            press_cycle(sender, address, args.hold, args.as_int, args.dry_run)

            if args.count and cycle >= args.count:

                break

            time.sleep(args.interval)

        print("------------------------------------")
        print("Готово - кнопка відпущена (надіслано 0).")
        print("Якщо реакції не було: перевірюй по черзі фокус вікна VRChat,")
        print("що предмет підсвічений саме цією рукою (Use/Grab) або вже в")
        print("руці (Drop), і що порт 9000 увімкнений у VRChat.")

    except KeyboardInterrupt:

        print()
        print("Зупинено вручну - відпускаю кнопку.")

        send(sender, address, 0 if args.as_int else False, args.dry_run)

    finally:

        sender.close()

    return 0


if __name__ == "__main__":

    sys.exit(main())
