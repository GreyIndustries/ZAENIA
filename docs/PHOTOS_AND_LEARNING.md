# Photos, learning library and Interlinear Bible

Available in the desktop app and connected browser app.

## Photos

Use the photo button beside the chat input. Select up to four JPEG, PNG or
WebP images, then type or speak a question. Sending with no question requests
a description. The same photos remain attached for follow-up questions until
you choose **Done with photos**. Selecting or removing a photo resets the photo
conversation context.

Images are resized to at most 1600 pixels on the longest edge, stripped of
metadata, validated again by the server, and interpreted by the existing local
Ollama `qwen3.5:4b` model. The original file is unchanged. Photos and their
analysis remain in this app session and are not written to conversation memory.
Images cannot issue actions or bypass task/calendar review. An unavailable
vision model produces an error instead of silently answering without the image.

## Learning library

Open **Assistant**, then **Learning library**. Paste a public HTTPS webpage and
choose **Download and learn**, or open **Learn from downloaded text** to import
a TXT/Markdown file or paste text. You can also say `learn from https://…`.

The library stores searchable source excerpts, source titles, links, download
dates and content hashes in `data/assistant_platform/platform.sqlite3`. Related
questions automatically receive relevant saved excerpts as reference material.
This is retrieval learning, not model-weight training. Sources are claims to
evaluate; they never become instructions or change Zae's rules. Refreshing the
same URL replaces its indexed excerpts. Removing a source removes its retrieval
chunks as well. The existing client memory permissions control access.

Downloads use the existing bounded public-web reader: HTTPS only, no private
addresses, no ambient cookies or proxies, and each redirect revalidated. Pages
over the reader's text limit are labeled as shortened. Pasted text supports up
to one million characters per source. The library holds up to 2,000 sources.

## Interlinear Bible

The existing checked corpus at `data/scripture/corpus.sqlite3` contains all 66
books. Assistant now includes a reader: enter `Genesis 1:1`, `John 1:1`,
`1 John 4:8` or a STEP reference such as `Psa.103.1`. Verse references in chat
also supply interlinear source evidence to the local model.

The reader shows original Hebrew/Greek, transliteration, English glosses,
Strong's references, morphology and source variant markers, alongside ASV 1901
and WEB Classic translations. It preserves the corpus's numbering warning.

Credit: [STEP Bible / Tyndale House Cambridge](https://github.com/STEPBible/STEPBible-Data),
CC BY 4.0. ASV 1901 and WEB Classic English texts from eBible.org are public domain.
Packaged corpus hashes and attribution files remain in `data/scripture/`.
