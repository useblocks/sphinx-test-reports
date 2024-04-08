import re


def tr_link(app, need, needs, test_option, target_option, *args, **kwargs):
    if test_option not in need:
        return ""
    test_option_value = need[test_option]
    if test_option_value is None or len(test_option_value) <= 0:
        return []

    links = []
    test_pattern = re.compile(test_option_value)
    for need_target in needs.values():
        # Skip linking to itself
        if need_target["id"] == need["id"]:
            continue

        if target_option not in need_target:
            continue

        target_option_value = need_target[target_option]
        if (
            target_option_value is not None
            and len(target_option_value) > 0
            and test_pattern.match(target_option_value)
        ):
            links.append(need_target["id"])

    return links
