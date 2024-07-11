def entity_to_char(entity):
    """
    Given an HTML entity, return the character it represents.
    ex. entity_to_char("&amp;") -> "&"
    """
    numeric_part = entity.replace("#", "").replace(";", "").replace("&", "")
    try:
        return chr(int(numeric_part, 10))
    except ValueError as e:
        return f"There is a problem with the entity passed: {e}"
