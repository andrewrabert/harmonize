class SubstitutionError(Exception):
    pass


def substitute(template, variables):
    """Substitute {var} placeholders in a list of command template strings.

    Supports {{/}} escaping for literal braces. Errors on unknown variables
    or unmatched braces.

    :param list[str] template: Command template strings
    :param dict variables: Variable name -> value mapping
    :returns: List of substituted strings
    :raises SubstitutionError: On unknown variable or unmatched braces
    """
    return [_substitute_string(s, variables) for s in template]


def validate_template(template, allowed_variables):
    """Validate that a command template only uses known variables.

    :param list[str] template: Command template strings
    :param set allowed_variables: Set of allowed variable names
    :raises SubstitutionError: On unknown variable or unmatched braces
    """
    dummy = {name: "" for name in allowed_variables}
    for s in template:
        _substitute_string(s, dummy)


def _substitute_string(s, variables):
    result = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "{":
            if i + 1 < len(s) and s[i + 1] == "{":
                result.append("{")
                i += 2
            else:
                end = s.find("}", i + 1)
                if end == -1:
                    raise SubstitutionError(
                        f"Unmatched opening brace at position {i} in: {s}"
                    )
                name = s[i + 1 : end]
                if name not in variables:
                    raise SubstitutionError(
                        f"Unknown variable {{{name}}} in: {s}"
                    )
                result.append(str(variables[name]))
                i = end + 1
        elif ch == "}":
            if i + 1 < len(s) and s[i + 1] == "}":
                result.append("}")
                i += 2
            else:
                raise SubstitutionError(
                    f"Unmatched closing brace at position {i} in: {s}"
                )
        else:
            result.append(ch)
            i += 1
    return "".join(result)
