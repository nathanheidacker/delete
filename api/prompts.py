parsability_prompt = """
You are given a Product Requirements Document (PRD) written in markdown.
Analyze it and identify areas that would be difficult for an LLM to properly parse.
Focus your improvements on areas that would help an LLM to understand the requirements of the feature being proposed.
The document will ultimately be used to automatically generate test cases.
For each issue found, provide:
- A short description
- A reference to the location(s) (line number or text snippet)
Return the result as a JSON array where each object has:
- "description": A short summary of the issue
- "locations": An array of instances of the issue occuring (e.g., line number or snippet)

Justifying the identified issues is very important, so please try your best to provide examples in the 'location' field
unless none exist.

PRD Document:
{prd}
""".strip()

consistency_prompt = """
You are given a Product Requirements Document (PRD) written in markdown.
Analyze it and identify inconsistencies, such as contradictory terminology or unclear design decisions.
The document will ultimately be used to automatically generate test cases, so the requirements should be thorough and clear.
For each issue found, provide:
- A short description
- A reference to the location(s) (line number or text snippet)
Return the result as a JSON array where each object has:
- "description": A short summary of the issue
- "locations": An array of instances of the issue occuring (e.g., line number or snippet)

Justifying the identified issues is very important, so please try your best to provide examples in the 'location' field
unless none exist.

PRD Document:
{prd}
""".strip()

completeness_prompt = """
You are given a Product Requirements Document (PRD) written in markdown.
Analyze it and identify issues with completeness. What elements are missing from the document or lacking in explanation?
The document will ultimately be used to automatically generate test cases, so the requirements should be thorough and clear.
For each issue found, provide:
- A short description
- A reference to the location(s) (line number or text snippet)
Return the result as a JSON array where each object has:
- "description": A short summary of the issue
- "locations": An array of instances of the issue occuring (e.g., line number or snippet)

Justifying the identified issues is very important, so please try your best to provide examples in the 'location' field
unless none exist.

PRD Document:
{prd}
""".strip()

clarity_prompt = """
You are given a Product Requirements Document (PRD) written in markdown.
Analyze it and identify issues with clarity, especially with the requirements.
The document will ultimately be used to automatically generate test cases, so the requirements must be thorough and clear.
For each issue found, provide:
- A short description
- A reference to the location(s) (line number or text snippet)
Return the result as a JSON array where each object has:
- "description": A short summary of the issue
- "locations": An array of instances of the issue occuring (e.g., line number or snippet)

Justifying the identified issues is very important, so please try your best to provide examples in the 'location' field
unless none exist.

PRD Document:
{prd}
""".strip()
