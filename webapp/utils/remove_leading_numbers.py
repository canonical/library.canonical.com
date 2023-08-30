def remove_leading_numbers(text):
    """
    Removes the number and dash(-) from a string
    ex. '4-Organisation' becomes 'Organisation'
    """
    if "-" in text:
        idx = text.index("-")
        if text[:idx].isdigit():
            index = idx + 1
            return text[index:]
    return text
