# Prompt

## the context

2026-January-17-Saturday

I used [codemerge][CM] to create a single-file from the [repo][RP] code, and uploaded that  file to ChatGPT.

I then added the prompt below. Everything after the prompt is the plan it came up with.

Version: ChatGPT-5.2-extended-thinking.

Note: the markdown produced doesn't render bullet-indents properly using Sublime's vanilla "markdown" profile. But using its "github" profile does render them properly.

[CM]: <https://github.com/gelleson/codemerge>
[RP]: <https://github.com/Brown-University-Library/pdf_checker_project>

# the prompt

In the initial version of this `pdf_checker_project`, if a user selected a pdf and then clicked "Check Accessibility", the webapp-code would, in real-time, run veraPDF, and then hit openrouter for a summary of the veraPDF output.

I thought that would take too much time, and so re-architected the webapp to "finish" its work on a "Check Accessibility" click quickly, and then poll, via htmx, for the results of the veraPDF-check and openrouter-call (which would be triggered by cronjobs).

But -- it turns out the direct calls _won't_ take too much time.

The desire: I'd like to update the code to:
- _try_ calling veraPDF (with a 30-second-max timeout),
- and then _try_ calling openrouter (with a 30-second-max timeout).
- but if the max-times are reached, the normal polling will take place.

So, the task:
- review the AGENTS.md file in the uploaded single-file `pdf_checker_project.txt` file (which is a flattened file containing all the repo files.)
- make a plan to programmatically update the code according to my desire -- and name it "PLAN__run_synchronously_with_timeouts.md"

---
