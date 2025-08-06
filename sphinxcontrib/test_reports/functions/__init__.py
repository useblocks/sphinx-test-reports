from typing import List, Dict


def tr_link(
    app: object,
    need: Dict[str, str],
    needs: Dict[str, Dict[str, str]],
    test_option: str,
    target_option: str,
    *args: object,
    **kwargs: object
) -> List[str]:
    if test_option not in need:
        return []

    # Allow for multiple values in option
    test_opt_values: List[str] = [s.strip() for s in need[test_option].split(",")]

    links: List[str] = []
    for need_target in needs.values():
        if target_option not in need_target:
            continue
        for test_opt in test_opt_values:
            if (
                test_opt == need_target[target_option]
                and test_opt is not None
                and len(test_opt) > 0  # fmt: skip
            ):
                links.append(need_target["id"])

    return links
