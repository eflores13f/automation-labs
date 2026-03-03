from health_report import take_snapshot, render_text, save_report


def main() -> None:
    snap = take_snapshot()
    report = render_text(snap)
    print(report)

    out_path = save_report(report)
    print(f"Saved report to: {out_path}")


if __name__ == "__main__":
    main()
