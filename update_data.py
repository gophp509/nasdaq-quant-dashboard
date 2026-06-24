from __future__ import annotations

from nasdaq_quant.updater import update_all


def main() -> None:
    status = update_all()
    print("data_status.json updated")
    print(status)


if __name__ == "__main__":
    main()
