import re


def extract_leading_number(name):
    """
    Extracts the leading number from a string.
    ex. '4-Organisation' returns 4
    """
    if name.lower() == "index":
        return 0000
    match = re.match(r"(\d+)-", name)
    if match:
        return int(match.group(1))
    return None


def remove_leading_number(name):
    """
    Removes the leading number and dash from a string.
    ex. '4-Organisation' becomes 'Organisation'
    """
    match = re.match(r"(\d+)-", name)
    if match:
        return name[match.end() :]  # noqa: E203
    return name
