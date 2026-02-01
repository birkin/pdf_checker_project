# About the experimental PDF Accessibility Checker

- [Purpose](#purpose)
- [Limitations](#limitations)
- [veraPDF](#verapdf)
- [this webapp's output](#this-webapps-output)
- [Usage](#usage)

---


## Purpose 

This is an _experimental_ webapp. It has the following purposes:

- To see if we could use a large-language model (LLM) to give staff and users friendly, useful, concrete suggestions for making their PDFs accessible.

- To experiment with an "upload and hand-off-to-a-model" architecture because it could be extremely useful for improving the accessibility of a variety of other media -- such as uploading images for suggested alt-text, and audios/videos for suggested description and/or captions. 

- To show [OIT][oit] and [CCV][ccv] a working version of this architecture -- so we can explore ways we mightwork with them to use their models for improved privacy, quality, and scalability. 

---


## Limitations

### Privacy

**Don't submit anything you want to keep private.** 

We don't send the PDF directly to any models, only the parsed-report, which doesn't contain detailed content information. But we may experiment with the the data that is sent to the models, so just to be safe, don't submit anything you want to keep private.

Official Brown models offer privacy guarantees that this webapp doesn't. 

### Capability

Currently, we're using a free [OpenRouter][or] account, using one of three free models, which are less capable than models we hope to use in the future. 

### Scalability

Our free account is limited to 50 requests per day. 

Due to this, we're initially only opening this up to library-staff. 

If this proves useful, and we're able to access a Brown model, we'll open this up to the Brown community, and eventually may implement API features on the drawing-board.

_If we're able to work with OIT and CCV to point to official Brown models, we'll note that here. That would address the privacy, capability, and scalability limitations._


---

## veraPDF

[veraPDF][vpdf] is a widely-used open-source tool for analyzing PDFs for digital-preservation and/or accessibility purposes. This webapp focuses specifically on accessibility.

Try out the veraPDF [demo][vpdf_demo] on their website.

veraPDF is terrific, but its output can be overwhelming for users. It uses a profile which contains a list of rules, and it checks every relevant PDF element against those rules. 

The result is that a PDF with 50 pages might generate thousands of failures -- even though it's possible that only a few fixes are needed to make the PDF accessible. 


---

## this webapp's output

This webapp runs veraPDF on the uploaded PDF. If failed checks are found, it parses the veraPDF output and sends the parsed-report, via OpenRouter, to a large-language model, with a prompt. The prompt: 

- asks for user-friendly [Acrobat][acrobat]-focused suggestions for making the PDF accessible, based on the examples of the failures.

- it asks for the best bang-for-the-buck suggestions so as not to overwhelm users.

Here is a [version of the prompt][prompt] (we'll be experimenting with it).

---


## Usage

Typically, you'll select and submit your PDF file. Usually within 20-seconds, you'll be redirected to the report page. Most of the time, the report page will show the suggestions at the top, and the raw veraPDF output can be toggled to appear below.

Copy the url if you want to review or share the report.

If something goes wrong, you'll still be directed to the report page, but it will show either a problem with the veraPDF check (rare), or a problem with the LLM suggestions (more common). Still, save that url and try to access it again later. We plan to implement a script to check for temporarily failed jobs and retry them.

Let us know via the feedback link on each page if you have any problems or questions.

---

[acrobat]: <https://get.adobe.com/reader/>
[ccv]: <https://ccv.brown.edu/>
[oit]: <https://it.brown.edu/>
[or]: <https://openrouter.ai/>
[prompt]: <https://github.com/Brown-University-Library/pdf_checker_project/blob/55eb02862fb5802e40aae3ba63f59333b83e7b28/pdf_checker_app/lib/openrouter_helpers.py#L23-L48>
[vpdf_demo]: <https://demo.verapdf.org/>
[vpdf]: <https://verapdf.org/>
