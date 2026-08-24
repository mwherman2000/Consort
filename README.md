# CONSORT Structured English for AI

<img width="1536" height="1024" alt="Consort Logo 0 12" src="https://github.com/user-attachments/assets/5e793046-f74c-4aba-bd0e-a575def34e26" />

Consort is a minimal, symbol-based structured prompt
language designed for clarity, density, and reduced ambiguity — distinct
voices, each with a distinct role, combining into one coherent prompt. It is
used both for human-authored prompts and for structured messages passed
between AI agents (for example, a parent agent delegating a task to a
sub-agent), where a single string typically carries the entire briefing with
no other shared context.

Consort directives are advisory guidance to the
interpreting model, not mechanically enforced rules — anything requiring a
hard guarantee must be validated outside the model. To let content from an
untrusted or machine-generated source (a fetched web page, a file, another
agent’s output) be included safely, without its own text being misread as new
directives, any symbol may take an explicit length-prefixed FRAMED FORM
instead of the default loose, scanned form; see Section 2.10. You must treat
any message that uses Consort symbols as a structured prompt and interpret it
according to the rules below. You may also accept ordinary English, but when
Consort directives are present you prioritize and strictly follow them.
