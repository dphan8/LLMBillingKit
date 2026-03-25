from types import SimpleNamespace

from tabulate import tabulate

from LLMBillingKit import track
from LLMBillingKit.db import query_by_customer


class FakeResponse:
    """Minimal response object that matches the attributes track() expects."""

    def __init__(self, request_id: str, model: str, prompt_tokens: int, completion_tokens: int):
        self.id = request_id
        self.model = model
        self.usage = SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


def main() -> None:
    responses = [
        FakeResponse("demo-req-1", "gpt-4o", 320, 120),
        FakeResponse("demo-req-2", "gpt-4o-mini", 520, 80),
    ]

    for response in responses:
        event = track(response, charged=0.02, customer="example_customer")
        if event is None:
            print(f"Skipped tracking for request {response.id}")
        else:
            print(
                f"Tracked {event['request_id']} | model={event['model']} | "
                f"cost=${event['actual_cost']:.6f} | margin=${event['margin']:.6f}"
            )

    rows = query_by_customer()
    if not rows:
        print("No data found. Run the script again or check your DB path.")
        return

    table = [
        [
            r["customer"],
            r["calls"],
            f"${r['total_charged']:.6f}",
            f"${r['total_cost']:.6f}",
            f"${r['total_margin']:.6f}",
        ]
        for r in rows
    ]
    print("\nCurrent customer margin report:\n")
    print(tabulate(table, headers=["Customer", "Calls", "Charged", "Cost", "Margin"]))


if __name__ == "__main__":
    main()
