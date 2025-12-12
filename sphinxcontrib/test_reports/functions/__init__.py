from typing import Dict, List, Union


def tr_link(
    app: object,  # Typed as object since the exact type is unknown
    need: Dict[
        str, Union[str, int]
    ],  # Keys are strings, values are strings or integers
    needs: Dict[str, Dict[str, Union[str, int]]],  # Nested dictionary
    test_option: str,
    target_option: str,
    *args: object,
    **kwargs: object,
) -> List[str]:
    if test_option not in need:
        return []

    # Allow for multiple values in option
    test_opt_values: List[str] = str(need[test_option]).split(",")

    links: List[str] = []
    for need_target in needs.values():
        if target_option not in need_target:
            continue
        for test_opt_raw in test_opt_values:
            test_opt: str = test_opt_raw.strip()
            if (
                test_opt == need_target[target_option]
                and test_opt is not None
                and len(test_opt) > 0  # fmt: skip
            ):
                links.append(str(need_target.get("id", "")))

    return links
