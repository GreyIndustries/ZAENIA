/** Public identity metadata. No authorization or private information is exposed. */
export const ZAENIA_IDENTITY_DESCRIPTION = "Zack’s Ædaptive, Neural, Intelligent Agent";
export const ZAENIA_IDENTITY_REPLY =
  "I am ZÆNIA, Zack’s Ædaptive, Neural, Intelligent Agent. My everyday role is your Assisting System.";

/** Only direct questions about the assistant's identity are intercepted locally. */
export function isZaeniaIdentityQuestion(input: string): boolean {
  const text = input
    .trim()
    .toLowerCase()
    .replace(/[’‘]/g, "'")
    .replace(/æ/g, "ae")
    .replace(/\b(?:z\s*[.\-]?\s*a\s*[.\-]?\s*e\s*[.\-]?\s*n\s*[.\-]?\s*i\s*[.\-]?\s*a)\b/g, "zaenia")
    .replace(/[!?.,]/g, "")
    .replace(/\s+/g, " ");
  return /^(?:what(?:'s| is) your name|who are you|tell me your name|say your name|introduce yourself|what (?:does|do) zaenia (?:stand for|mean)|what is (?:the )?meaning of (?:the name )?zaenia|what is zaenia's (?:full name|acronym)|(?:expand|explain|spell out) (?:the )?(?:zaenia )?acronym|what does your name mean|what does your name stand for|what is your full name|tell me (?:the meaning of|what) zaenia (?:means|stands for)|what does z a e n i a stand for)$/i.test(text);
}
