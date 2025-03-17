def extract_codeblocks(markdown: str) -> list[str]:
    codeblocks = []
    current_block = ""
    is_block = False
    for line in markdown.split("\n"):
        if line.startswith("```"):
            if is_block:
                codeblocks.append(current_block)
                current_block = ""
            is_block = not is_block
            continue
        if is_block:
            current_block += line + "\n"
    if current_block:
        codeblocks.append(current_block)
    return codeblocks
