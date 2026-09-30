"""
osc_look_probe.py

Вимірювання ответа аватара на відомі значення осі погляду:
`/input/LookHorizontal` (і `LookVertical`).

Навіщо: код тримає нейтраллю `+0.5` (і `+0.1` для нахилу), тоді як
офіційна специфікація VRChat каже, що осі - це `-1 .. +1` і «expect to
reset to 0 when not in use». Яка з двох конвенцій справжня для твого
аватара - визначає, як саме виправляти карту значень, тому відповідь
потрібен виміряну, а не виведену з документації.

    python osc_look_probe.py --preset ladder        # драбина -1 .. +1
    python osc_look_probe.py --preset around        # мікрокрок біля нейтралі
    python osc_look_probe.py --from -1 --to 1 --step 0.1 --pingpong
    python osc_look_probe.py --axis LookVertical --preset around

Вимкни main.py на час вимірювання: він надсилає свої значення на кожному
кадрі і перекриє результат. Вікно VRChat має бути сфокусоване.
"""

from __future__ import annotations

import argparse
import sys
import time

from osc_sender import OSCSender


# ============================================================
# Parameters
# ============================================================

AXES = ("LookHorizontal", "LookVertical")

# Значення, які код погляду вважає «нейтраллю» - біля них і шукаємо поріг.
CENTERS = {
    "LookHorizontal": 0.5,
    "LookVertical": 0.1,
}

LADDER = (
    0.0, 0.25, 0.5, 0.75, 1.0,
    0.75, 0.5, 0.25, 0.0,
    -0.25, -0.5, -0.75, -1.0,
    -0.75, -0.5, -0.25, 0.0,
)


# ============================================================
# Sequences
# ============================================================

def ramp(start: float, stop: float, step: float):

    values = []

    current = start

    # Крок беремо за модулем: -1 -> 1 зі step 0.1 має йти вгору.
    direction = 1 if stop >= start else -1

    while (current - stop) * direction <= 1e-9:

        values.append(round(current, 6))

        current += direction * abs(step)

    return values


def around(center: float, width: float, step: float):

    return ramp(center - width, center + width, step)


def resolve_step(args) -> float:

    if args.step is not None:

        return args.step

    return 0.05 if args.preset == "around" else 0.1


def build_values(args) -> list:

    step = resolve_step(args)

    if args.preset == "ladder":

        # Драбина вже йде вгору й назад, тож pingpong їй не потрібен.
        return list(LADDER)

    if args.preset == "around":

        center = args.around if args.around is not None else CENTERS[args.axis]

        values = around(center, args.width, step)

    else:

        values = ramp(args.source, args.target, step)

    if args.pingpong:

        # Останнє значення не повторюємо: воно й так утримується один крок.
        values = values + values[-2::-1]

    return values


# ============================================================
# Report
# ============================================================

def print_protocol(address: str, values, hold: float, loops: int):

    print("Що робити під час прогону:")

    print("  1. сфокусуй вікно VRChat (клавіші й осі без фокусу не працюють);")

    print("  2. сядь нерухомо і НЕ рухай головою;")

    print("  3. на кожному значенні подивись, куди дивиться голова аватара,")

    print("     і запам'ятай/запиши номер кроку.");

    print()

    print(f"  Крок:   {address}        що бачу (заповниш і скинеш мені)")

    print("  -----   -------------   ---------------------------------")

    for i, value in enumerate(values, start=1):

        print("  {:>4}    {:+.3f}        ".format(i, value) + "." * 28)

    print()

    print(f"  {len(values)} кроків по {hold} с = {len(values) * hold:.0f} с на цикл, циклів: {loops}")


# ============================================================
# Main
# ============================================================

def build_parser():

    parser = argparse.ArgumentParser(
        description="Вимірювання ответа осі погляду на відомі значення.",
    )

    parser.add_argument(
        "--axis",
        default="LookHorizontal",
        choices=AXES,
        help="вісь, яку міряємо (типово LookHorizontal)",
    )

    parser.add_argument(
        "--preset",
        default="ladder",
        choices=("ladder", "around", "custom"),
        help="ladder = драбина -1..+1; around = мікрокрок біля нейтралі; custom = свої межі",
    )

    parser.add_argument("--around", type=float, default=None, help="центр для around (типово 0.5 / 0.1 для осі)")
    parser.add_argument("--width", type=float, default=0.1, help="наскільки широко навколо центра (типово 0.1)")
    parser.add_argument("--source", type=float, default=-1.0, help="початок для custom")
    parser.add_argument("--target", type=float, default=1.0, help="кінець для custom")
    parser.add_argument("--step", type=float, default=None, help="крок (типово 0.05 для around, 0.1 для custom)")
    parser.add_argument(
        "--pingpong",
        action="store_true",
        help="пройти драбину ще й у зворотному напрямку - так видно гістерезис",
    )
    parser.add_argument("--hold", type=float, default=2.0, help="секунд на кожне значення")
    parser.add_argument("--loop", type=int, default=1, help="кількість повторів послідовності")
    parser.add_argument("--start-delay", type=float, default=8.0, help="час на те, щоб перемкнути фокус у VRChat")
    parser.add_argument("--finish", type=float, default=None, help="значення в кінці (типово 0.0)")
    parser.add_argument("--dry-run", action="store_true", help="лише показати послідовність")

    return parser


def main(argv=None) -> int:

    args = build_parser().parse_args(argv)

    values = build_values(args)

    address = f"/input/{args.axis}"

    sender = OSCSender()

    print("------------------------------------")
    print(f"Вісь       : {address}")
    print(f"Нейтраль коду : {CENTERS[args.axis]}  (що код видає, коли ти нерухомий)")
    print(f"Значень    : {len(values)}   утримання: {args.hold} с   циклів: {args.loop}")
    print(f"Куди       : {sender.ip}:{sender.port}   режим: {'dry-run' if args.dry_run else 'надсилання'}")
    print("------------------------------------")

    if not values:

        print("Порожня послідовність - перевір --from/--to/--step.")

        return 1

    print_protocol(address, values, args.hold, args.loop)

    print("------------------------------------")

    if args.dry_run:

        for i, value in enumerate(values, start=1):

            print(f"   [dry-run] {i:>3}  {address} = {value:+.3f}")

        return 0

    if args.start_delay > 0:

        print(f"Перемкни фокус у VRChat - є {args.start_delay:.0f} с...")

        time.sleep(args.start_delay)

    try:

        for cycle in range(max(1, args.loop)):

            if args.loop > 1:

                print(f"Цикл {cycle + 1} з {args.loop}")

            for i, value in enumerate(values, start=1):

                sender.client.send_message(address, float(value))

                print(f"   {i:>3}  {address} = {value:+.3f}   <- що бачиш?")

                time.sleep(args.hold)

    except KeyboardInterrupt:

        print()

        print("Зупинено вручну.")

    finish = 0.0 if args.finish is None else args.finish

    sender.client.send_message(address, float(finish))

    print(f"    -> у кінці надіслано {address} = {finish:+.3f}")

    print("------------------------------------")
    print("Скинь мені заповнені рядки «що бачиш» - за ними вирішимо карту.")

    sender.close()

    return 0


if __name__ == "__main__":

    sys.exit(main())
