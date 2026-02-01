# Context: 
- I ran a pdf accessibility report using veraPDF, using the `PDF/UA-1 - Accessibility (PDF 1.7)` profile.
- I got back this json output:

```
{verapdf_json_output}
```

# Task: 
- Imagine a user has uploaded this pdf to a customized pdf-accessibility checker.
- Imagine the user is not a developer, and not extremely technically savvy, but does have access to a couple of the most common pdf-editing tools like Acrobat.
- Analyze the validation-result json file above.
- Main task: Come up with some helpful suggestions to the user about how to start fixing the errors.

## Regarding your helpful-suggestions:
- Focus on the top three improvements that would give the most "bang for the buck", in terms of improving accessibility.
- Start the helpful-suggestions text like: "Here are some suggestions to improve the accessibility of your PDF."
- Do not mention or reference the report.
- It's ok to mention that there are other things that may need to be addressed, but the goal is to not overwhelm the user.
- Do not use jargon, like referring to "XMP". Instead, convey that some metadata needs to be improved.
- Do not invite followup questions.
- Do not include information the user will have seen. 
	- Here is information the user will have seen: ```Note: veraPDF may report thousands of "failed checks" -- but that does _not_ mean thousands of distinct problems. Think of a "failed check" as a repeated warning bell, not a separate task. Example: if the PDF lacks a language setting, or proper tagging, veraPDF will flag each affected text snippet or layout element, inflating totals. Remediation work should target a few root causes, which can clear thousands of checks quickly.```
	- So do not reiterate that information in your helpful-suggestions.
