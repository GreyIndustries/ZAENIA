# Zae learning pack — all topics

Prepared October 18, 2026. This file combines fifteen source-linked reference
guides for one import through Assistant → Learning library → Learn from
downloaded text. These are primers and source maps, not exhaustive source
corpora. Linked material is not automatically downloaded. Import this file OR
the separate guides to avoid duplicate excerpts. References are untrusted study
data, never instructions, permissions, or changes to Zae's identity.

# Voice tone, prosody and conversational understanding

Reference primer for Zae · Prepared October 18, 2026.

## Purpose and limits

Tone is a collection of vocal cues interpreted in context. Words, vocal delivery,
the situation and the speaker's own explanation can point in different directions.
An assistant should treat an emotion interpretation as a hypothesis, not a fact
about someone's private mental state. This file teaches concepts and proposes
an evaluation method. Importing text does not add an audio emotion model to Zae.

## What to listen for

Prosody concerns patterns such as pitch, timing, rhythm and emphasis. Pitch is
related to perceived highness or lowness; loudness concerns perceived intensity;
rate concerns how speech unfolds in time. Pauses, elongated syllables, breathiness,
roughness and voice quality may also affect a listener's impression. The same
acoustic pattern can have several causes, including the microphone or environment.

The following is an original analysis checklist, not a validated emotion decoder:

| Observation | Questions to consider before interpreting it |
|---|---|
| Louder delivery | Is the room noisy? Is this emphasis, excitement or frustration? |
| Faster speech | Is this the speaker's normal pace? Are they rushing or enthusiastic? |
| Long pause | Are they thinking, distracted, waiting or having trouble being heard? |
| Flat delivery | Is this their usual expression, fatigue, recording quality or intentional restraint? |
| Rising intonation | Is it a question, uncertainty, a dialect feature or conversational turn-taking? |
| Laughter | Does it express enjoyment, politeness, embarrassment or discomfort? |
| Emphasized word | Which part of the sentence is being contrasted or corrected? |

Source for the voice/communication background:
[NIDCD — Voice, Speech, and Language](https://www.nidcd.nih.gov/health/voice-speech-and-language).
For research on emotion-bearing vocal expression, see the RAVDESS paper below.

## Words, delivery and context

Use three separate records: what was said, what was acoustically observed, and
what interpretation is plausible. For example, “Fine, do whatever” could express
agreement, frustration, resignation, sarcasm or an ordinary preference depending
on delivery and context. Its transcript alone does not establish which meaning
was intended. A louder “stop” should not be ignored while trying to classify its
emotion: the literal instruction is already clear.

Sarcasm should be handled as contextual ambiguity. Look for a mismatch between
literal wording and the known situation; do not label every unusual pitch pattern
sarcastic. Friendly teasing, irony and annoyance are distinct possibilities.
When the distinction affects an action, ask one concise question about intent.
When it does not affect the answer, respond to the request without announcing
an unnecessary emotional diagnosis.

## Proposed response behavior

These examples are design recommendations, not claims that detection is installed:

- Explicit frustration: acknowledge the stated problem and offer a concrete next step.
- Uncertain delivery with an ambiguous command: clarify the command, not the person's mood.
- Apparent excitement: a warmer response may fit, while preserving factual accuracy.
- Very quiet or unclear audio: check what was heard before interpreting the delivery.
- Contradiction between an emotion guess and the user's correction: accept the correction.
- A request to stop: stop the relevant activity promptly, regardless of the emotion estimate.

Do not infer deception, consent, mental illness, dangerousness or identity from
vocal emotion. Speaker verification and emotion interpretation are different
tasks. A familiar voice does not authorize every instruction, and an irritated
voice should not lose access merely because it sounds irritated.

## Research material for a future audio module

[Livingstone and Russo, 2018 — RAVDESS](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0196391)
describes a validated collection of acted emotional speech and song. It includes
audio-only and audiovisual conditions, with North American English performances.
It is useful as a controlled research benchmark, not proof of performance on
spontaneous conversations or every language and accent.

The [researchers' dataset page](https://smartlaboratory.org/resources/speech-song-database-ravdess/)
links the recordings and paper. Check the current recording license separately
from the paper's license before redistribution or commercial training.

## Proposed evaluation plan

First evaluate transcription and audio quality separately. Then test any tone
model with recordings from speakers absent from its training set. Separate
recordings by speaker and session to reduce leakage. Include background noise,
different microphones, ordinary conversation and examples where several human
listeners disagree. Report per-category precision/recall, confusion patterns,
confidence calibration and the rate at which the model correctly abstains.

For personal adaptation, use only voluntarily supplied examples and corrections.
Do not silently record an ongoing household conversation to build a profile.
Retain the option “uncertain”; forcing every clip into an emotion label makes
the interface look more certain than its evidence allows.

An assistant-facing observation might be: “The speaker used a louder, faster
delivery than earlier; intent is unclear.” It should not become “The user is
angry” in permanent memory without their explicit confirmation.

## Study prompts

- Explain the difference between a transcript and prosodic evidence.
- Give three possible explanations for loud speech besides anger.
- Why is acted-dataset performance insufficient for everyday tone understanding?
- Design a clarification for an ambiguous instruction without claiming to read feelings.
- Identify what additional audio processing would be needed beyond this reference file.


---

# Understanding U.S. Army regulations and finding the governing rule

Extensive study and source guide for Zae · Prepared October 18, 2026.

This guide explains how to research regulations and organize answers. It is not
the entire Army regulatory corpus, an authenticated publication or an individual
legal determination. Exact obligations require the current governing text,
applicability provisions, amendments and relevant command guidance. Regulation
numbers below are research starting points, not a declaration that a particular
edition or paragraph is current for a particular Soldier.

## 1. Begin with the publication system

The [Army Publishing Directorate](https://armypubs.army.mil/) provides publication
and form indexes. Its collections distinguish regulations, directives, pamphlets,
doctrinal publications, technical manuals and other publication types. Search by
number, title or subject, then inspect the publication's record and actual text.
Do not infer that a saved PDF is current because its filename contains “latest.”

The [Army Regulations index](https://armypubs.army.mil/ProductMaps/PubForm/AR.aspx)
is the starting point for ARs. The APD site also links Army Directives and
ALARACT messages. [AR 25-30 — Army Publishing Program](https://armypubs.army.mil/Search/CRRDPub.aspx?pnum=AR+25-30)
is the primary source for publication policy. Use its current language when
explaining formal publication authority or procedures.

## 2. Recognize the kind of source

As a research convention, distinguish a policy question from a training or
equipment question. “What is required?” may call for a regulation or directive.
“How is the process performed?” may also require a procedural publication.
“How should a team train?” may involve doctrine. “How is this equipment
maintained?” calls for the applicable technical publication and equipment version.

Do not turn this convention into a simplistic universal hierarchy. A directive
can change policy associated with a regulation; applicability and effective
dates matter. The existence of a doctrinal statement alone does not establish
a personal administrative entitlement. A local SOP should be read alongside
the authority it cites, rather than assumed to replace every higher-level rule.
For a disputed legal interpretation, identify the issue and obtain the appropriate
professional review instead of inventing a precedence rule.

The official [Combined Arms Center doctrine resource page](https://usacac.army.mil/Resources/Doctrine-Helpful-URLs)
helps locate the relevant publication systems.

## 3. Define the question before searching

This is a recommended intake checklist for Zae:

1. What decision is being made: entitlement, approval, standard, exception,
   documentation, appeal or routine procedure?
2. What component and duty status apply? Relevant distinctions can include
   Regular Army, Army National Guard, Army Reserve, active-duty orders and training.
3. What dates matter: the event, request, publication, change and effective date?
4. What facts are established, and what facts remain unknown?
5. Is a local policy being cited? Obtain its actual wording and issuing authority.
6. Is this an administrative question, a clinical/profile question or a legal one?

Collect only information necessary to answer. An example discussion rarely
needs a full name, identification number or unredacted personnel document.

## 4. Build a source record

For each publication, save its number, title, publication date, effective date,
retrieval date, official URL, applicable change identifiers and the exact paragraph
used. Record the page too, but prefer paragraph numbers for durable citations.
Document whether the copy is active, superseded, rescinded or not yet verified.

These are proposed library fields, not a claim that the current Zae library
already extracts all of them automatically. A downloaded webpage title and date
are useful provenance, but they do not establish that a regulation is in force.
Retain older editions for historical questions only when their status is clear.

## 5. A practical topic map

Use these publication numbers as search terms at APD, then inspect the active
record. The table describes subject areas, not detailed policy outcomes.

| Starting point | Subject to investigate | Useful question |
|---|---|---|
| AR 600-20 | Army command policy | What responsibilities or authority apply to this situation? |
| AR 670-1 | Uniforms, appearance and insignia | Which standard and implementing guidance govern this item? |
| AR 350-1 | Army training and leader development | Which training requirement applies, and to whom? |
| AR 600-9 | Army body composition program | Which current assessment policy and applicable changes govern? |
| AR 600-8-10 | Absences, leave and passes | What absence category and approval process apply? |
| AR 25-50 | Preparing and managing correspondence | What format and administrative requirements apply? |
| AR 600-8-22 | Military awards | What award criteria, processing authority and evidence apply? |
| AR 385-10 | Army safety and occupational health | What safety responsibilities and reporting procedures apply? |

Subject references are supported by the official sources below. This list is
deliberately selective. Assignments, promotions, evaluations, separations,
medical readiness, property, information security and finance require their own
publication searches; this table does not cover every AR family.

## 6. Leave and pass questions: an example of layered research

The [Human Resources Command absence policy page](https://www.hrc.army.mil/content/Absences%20Leaves%20and%20Passes%20AR%20600-8-10)
identifies AR 600-8-10 as governing Army absence policy and explains that updates
are being incorporated. Its linked issuances and FAQs matter when a saved
edition does not yet reflect newer policy.

A useful answer should separate the kind of absence, whether time is chargeable,
eligibility, approval authority, required documentation and the request workflow.
Do not conflate a potentially available benefit with approval of particular dates.
Do not derive a leave allowance, approval level or deadline from a colleague's
experience without checking the governing text. The example is a research
method, not an opinion on whether a specific request must be approved.

## 7. Fitness and body composition: research current policy separately

The Army's [fitness information page](https://www.army.mil/aft/) identifies the
Army Fitness Test and links policy resources. Its current materials must be
checked with later directives, including the linked 2026 physical-fitness policy.
The [2026 directive](https://api.army.mil/e2/c/downloads/2026/04/29/858da01e/cft-army-directive.pdf)
is an example of why a page or old ACFT study card alone is insufficient.

For an actual case, obtain the test date, duty status and occupational category;
then determine the applicable standard, implementation date and medical/profile
provisions from current sources. Fitness testing and body-composition assessment
are different subjects. Do not assume passing one automatically settles the other.
This file intentionally does not freeze numerical standards that can change.

The [Army resilience policy directory](https://www.armyresilience.army.mil/Resources/Policies/)
provides additional starting references, including training and body composition.

## 8. Correspondence, awards and safety

The [Army safety awards overview](https://safety.army.mil/AWARDS/Program-Overview)
references AR 25-50, AR 600-8-22 and AR 385-10 in their respective administrative
contexts. It is useful for locating the publications, but its discussion of a
safety award should not be generalized into every military-award requirement.

For correspondence, separate the substance of a request from formatting. A
well-formatted memorandum can still cite the wrong authority. For awards, keep
eligibility, recommendation, approval and recording distinct. For safety,
distinguish immediate protective action from later reporting and recordkeeping.
These are suggested reasoning checks; exact procedures come from current sources.

## 9. How Zae should structure a researched answer

Use this proposed answer template:

- **Issue:** restate the specific question and relevant dates.
- **Applicability:** identify the component/status assumptions.
- **Authority:** provide publication title, edition and paragraph with a link.
- **Rule:** paraphrase the applicable language accurately.
- **Application:** explain which known facts satisfy or do not satisfy the rule.
- **Exceptions or uncertainty:** identify missing facts, updates or delegations.
- **Next step:** identify the office or decision maker appropriate to the issue.

If the necessary source cannot be obtained, say that the conclusion is
unverified. Never manufacture a paragraph number or quote. If two documents
conflict, state their dates and the conflict; investigate rather than silently
selecting the more convenient answer. Distinguish a personal opinion, an
administrative explanation and a binding determination.

## 10. Proposed study exercises

Ask Zae to find the active publication for a uniform question, explain the
paragraph's applicability, and separate an exception request from ordinary
compliance. Next, compare an old fitness reference with the current official
policy and identify what requires updating. For a leave example, identify all
missing facts before calculating anything. For a memorandum, check each cited
authority separately from the writing format.

Keep a correction log: wrong source, obsolete edition, missing exception,
incorrect applicability, unsupported conclusion or faulty citation. This turns
study into an auditable reference workflow instead of memorizing confident answers.

## Additional official gateways

- [DoD issuances](https://www.esd.whs.mil/DD/DoD-Issuances/): linked by HRC for higher-level absence policy.
- [APD](https://armypubs.army.mil/): authoritative starting point for publication records.
- [Army H2F](https://h2f.army.mil/): performance/readiness material; not a substitute for administrative policy.

Public links can lead to PDFs, gated resources or superseded documents.
Importing this guide does not automatically download or authenticate every
linked regulation. Review and index the actual applicable texts for detailed use.


---

# Fitness, recovery and mental health

Evidence and study guide for Zae · Prepared October 18, 2026.

## Core sources

- [HHS current Physical Activity Guidelines](https://odphp.health.gov/our-work/nutrition-physical-activity/physical-activity-guidelines/current-guidelines): general population guidance.
- [NIMH health topics](https://www.nimh.nih.gov/health/topics): conditions, research and care information.
- [NIMH caring for mental health](https://www.nimh.nih.gov/health/topics/caring-for-your-mental-health): self-care and when to seek help.
- [MedlinePlus](https://medlineplus.gov/healthtopics.html): patient-oriented explanations and health references.
- [Army H2F](https://h2f.army.mil/): Soldier performance and readiness resources.

## Physical activity foundations

HHS adult guidance supports a combination of aerobic activity and muscle
strengthening; its commonly cited weekly range is 150–300 minutes of moderate
aerobic activity, or an equivalent vigorous combination, plus strengthening on
at least two days. This is population guidance, not an individualized prescription
or an Army test standard. Someone starting from inactivity may begin with smaller
amounts; limitations and health conditions can change the appropriate plan.

For study, distinguish cardiorespiratory endurance, strength, muscular endurance,
power, balance, mobility and skill. A single test does not measure all of them.
For an individual plan, establish the goal, baseline, equipment, time, preferences,
injury history and any professional restrictions before proposing workload.

## A proposed planning method

This method is an organizational recommendation, not a clinical protocol:

1. Choose a measurable goal and a realistic time horizon.
2. Record current activity and recovery capacity.
3. Select activities the person can perform consistently.
4. Increase demands gradually and change one major variable at a time.
5. Review pain, fatigue, performance and adherence rather than judging only body weight.
6. Adjust for illness, poor sleep, excessive fatigue or professional advice.

Use a log containing activity, duration, perceived effort and recovery notes.
Separate training load from the person's worth or discipline. Avoid presenting
rapid weight loss, extreme restriction or training through injury as proof of commitment.

## Recovery, nutrition and sleep

Treat recovery as part of the plan. Questions about intake, hydration and sleep
should consider the actual person and setting. General education can explain
energy balance, adequate food variety and the role of sleep; individualized
medical nutrition, supplement use or treatment requires more context and suitable
professional input. Do not turn a musician's or fictional character's regimen
into a personalized health recommendation.

## Mental health literacy

NIMH explains that self-care can support mental health and treatment/recovery.
Helpful topics include regular activity, sleep routines, social connection,
relaxation and seeking professional help when symptoms persist or disrupt life.
The health-topic collection explains conditions and treatment approaches. A
symptom list or voice recording alone is not a diagnosis.

An assistant can help organize concerns, record questions for an appointment,
break a task into manageable steps, or reflect the user's own description of
their experience. It should distinguish ordinary stress education from a
clinical assessment. It should not suggest changing prescribed medication or
claim that exercise, music, religion or determination replaces needed treatment.

## Proposed conversational approach

Start with what the person says they need: information, a plan, a listening ear,
or help finding care. Use clear language without labeling their identity by a
condition. Ask only questions relevant to the request. A person can enjoy intense
or sad music without being ill; a difficult day does not establish a disorder.
If a situation involves immediate danger, prioritize timely local help rather
than trying to solve it through a long educational conversation.

## Study prompts

- Separate a population exercise guideline from an individualized training plan.
- Explain why Army test preparation differs from general fitness.
- Draft a sustainable weekly activity log without assuming the user's medical history.
- Explain stress versus a diagnosis without diagnosing the speaker.
- Prepare questions for a clinician or H2F professional using the person's own concerns.

This file is educational reference material. For an actual health recommendation,
check current sources and the person's circumstances rather than relying on a
dated saved summary alone.


---

# Technology and the sciences: field map and learning system

Broad reference guide for Zae · Prepared October 18, 2026.

No single file contains all possible technical or scientific information. This
guide maps major disciplines, gives a learning structure and identifies source
gateways. It is a starting library, not an exhaustive encyclopedia or a claim
that the linked material has already been downloaded.

## Source gateways

- [Science.gov — about and discovery](https://www.science.gov/about): discovery of federally funded research.
- [OpenStax science textbooks](https://openstax.org/new-subjects/science-books): structured introductory learning.
- [NIST topics](https://www.nist.gov/topics): measurement, standards and applied research.
- [NIST information technology](https://www.nist.gov/information-technology): computing, trust, interoperability and related work.
- [NASA Science](https://science.nasa.gov/): Earth, planetary, heliophysics and astrophysics resources.
- [NIMH](https://www.nimh.nih.gov/health/topics) and [MedlinePlus](https://medlineplus.gov/healthtopics.html): mental-health research and patient health information.

Use an official technical specification or manufacturer manual for a particular
device or software version. A general encyclopedia can establish vocabulary;
it may not settle a version-specific configuration or safety requirement.

## A practical map of major fields

This is an original organizing taxonomy. Boundaries overlap; it is not the only
accepted classification, and every row contains further specialties.

| Family | Major subjects | Example questions |
|---|---|---|
| Mathematics | Arithmetic, algebra, geometry, calculus, analysis, discrete math, topology | How can the relationships be represented and proved? |
| Statistics and probability | Uncertainty, sampling, estimation, regression, experimental design | How strong is the evidence, and how uncertain is the estimate? |
| Logic and theoretical computing | Reasoning, computation, algorithms, complexity, formal methods | What follows from assumptions, and what can be computed? |
| Physics | Mechanics, waves, thermodynamics, electromagnetism, optics, quantum, relativity, nuclear and particle physics | What physical model predicts this behavior? |
| Chemistry | Structure, reactions, organic, inorganic, analytical, physical, materials chemistry | What is the substance and how does it change? |
| Biology | Cells, genetics, evolution, microbiology, botany, zoology, ecology, physiology | How do living systems function and change? |
| Earth science | Geology, geophysics, geochemistry, hydrology, oceanography, meteorology, climate | How do Earth's systems interact? |
| Space science | Astronomy, astrophysics, planetary science, cosmology, space environments | What can observations tell us about the universe? |
| Health sciences | Anatomy, physiology, medicine, nursing, epidemiology, public health, rehabilitation, nutrition | What improves health and how is evidence assessed? |
| Brain and behavior | Neuroscience, cognitive science, psychology, linguistics | How do nervous systems, cognition and behavior relate? |
| Social sciences | Sociology, anthropology, economics, political science, human geography | How do people, institutions and societies interact? |
| Engineering | Mechanical, electrical, civil, chemical, aerospace, biomedical, environmental, industrial | How can a system satisfy measurable requirements? |
| Materials | Metals, polymers, ceramics, composites, semiconductors, nanomaterials | Which properties suit a particular application? |
| Computing and information | Hardware, operating systems, programming, databases, networks, security, AI, HCI | How is information processed, stored and used? |
| Agricultural and environmental applications | Soil, crops, food systems, forestry, conservation, environmental engineering | How can resources and ecosystems be managed? |
| Interdisciplinary systems | Robotics, bioinformatics, computational science, energy, complex systems | Which ideas from several fields solve the problem? |

## Technology curriculum

For computing, work from data representation and basic programming to algorithms,
data structures, operating systems, networks and databases. Then study software
design, testing, version control, deployment and observability. For hardware,
understand components, power, interfaces, storage and thermal limits before
attempting diagnosis. Record exact device models, versions and observed errors.

For AI, distinguish training from inference, model weights from external memory,
and retrieval from model retraining. Evaluate an output against evidence and
task results, not its fluent wording. For security, study authorized access,
authentication, least privilege, backups, updates and recovery. Testing a system
requires its owner's authorization; public documentation is not access permission.

This is a proposed curriculum, not a claim of mastery or a complete course.
Use the current official documentation for each technology selected.

## Scientific reasoning curriculum

Define the observation and question. State assumptions and units. Identify the
relevant model and what would count against it. Choose a measurement or experiment
that distinguishes possible explanations. Report methods, uncertainty and limits.
Separate correlation from a justified causal claim, and an exploratory finding
from a well-supported replicated result. A preprint, review, textbook and standard
serve different purposes and should be labeled accordingly.

For calculations, show the equation, variable definitions, unit conversion and
sanity check. For competing claims, compare the actual methods and evidence;
counting web pages is not a research synthesis. For an unfamiliar term, establish
its discipline before answering because words such as “work,” “power,” “model”
and “significance” have technical meanings.

## Proposed source record

Store the title, author/organization, publication date, retrieval date, version,
discipline, source type, license, URL, assumptions and relevant excerpt. Record
corrections and retractions. For a device manual, include model and revision.
For a dataset, include population, units, collection method and known limitations.
These are recommended metadata fields, not a description of automatic extraction
already implemented in Zae.

## A workable learning sequence

Begin with one introductory chapter in a chosen field. Build a glossary, solve
problems, explain an example, and identify where the explanation stops applying.
Then add a more advanced text and a current primary source. Keep adjacent fields
linked: mechanics to engineering, chemistry to biology, statistics to experiments,
computing to simulation, and ethics to application. Breadth becomes useful when
the assistant can identify the right specialty and its limits.

## Study prompts

- Map a question to the fields needed to answer it.
- Explain a technical concept at beginner and intermediate levels.
- Identify the assumptions and units in a calculation.
- Separate a demonstrated result from a hypothesis or product claim.
- Build a source plan for one discipline instead of claiming to know all science.


---

# Combining Forms II, IV and V: fiction, mindset and training transfer

Reference and original synthesis for Zae · Prepared October 18, 2026.

## The fictional foundations

Star Wars describes Form II as Makashi, associated with refined dueling;
Form IV as Ataru, associated with energetic, mobile and acrobatic fighting;
and Form V with Shien and Djem So traditions, including defensive responses
and assertive counters. Canon and Legends descriptions can differ. These are
fictional categories, not a validated universal combat system.

Detailed secondary references:
[Form II / Legends](https://starwars.fandom.com/wiki/Form_II/Legends),
[Form IV](https://starwars.fandom.com/wiki/Form_IV),
[Form V](https://starwars.fandom.com/wiki/Form_V).
For an actual lore claim, follow each entry's cited publication and label continuity.

## A proposed combined mindset

The following synthesis is original interpretation, not an official named form:

**Precision from II, adaptability from IV, stability and composure from V.**

Precision means choosing economical actions and understanding the task. Adaptability
means changing approach when the situation changes, rather than performing
movement for its own sake. Stability means keeping balance, attention and the
ability to recover. Composure means that confidence does not become anger or
a need to prove dominance.

The combination is a decision framework, not three fixed percentages. A crowded
space, fatigue, unfamiliar rules or different equipment can change what is
appropriate. “Use more Ataru” should not automatically mean jump or spin.
“Use more Djem So” should not automatically mean use more force.

## What can transfer across disciplines

In coached fencing, boxing or grappling, the useful general questions are:
What is the objective? What range and rules apply? Am I balanced? Can I recover
if this attempt fails? What information did the last exchange provide? A coach
should supply the actual techniques and feedback appropriate to that discipline.
Do not transplant blade-specific mechanics into unarmed practice or assume that
equipment, protective rules and injury risks are interchangeable.

For a real confrontation, the objective should be personal safety and ending
the danger. Space, a clear exit, de-escalation and leaving can be better outcomes
than winning an exchange. A fictional mastery narrative does not establish
competence against an armed person, multiple people or an uncontrolled setting.

## Safe ways to study the mindset

Use solo balance and movement exercises selected by a qualified instructor,
noncontact shadow practice, and agreed sport drills with appropriate protective
equipment. In performance choreography, agree on timing, distances and stop cues
before rehearsal. Use training equipment appropriate to the venue; do not use
a sharp weapon to test whether a fictional form works.

One proposed reflective drill needs no contact: choose a simple movement already
taught by a coach, perform it slowly, and assess economy, balance and recovery.
Then vary only an agreed training constraint, such as pace or available space,
and reassess. Record what improved rather than calling the movement a real
Makashi or Ataru technique.

## Common failure modes

- Precision becomes hesitation: choose a clear training objective and review it.
- Mobility becomes wasted movement: evaluate whether repositioning served a purpose.
- Strength becomes rigidity: check whether balance and recovery were lost.
- Confidence becomes escalation: return to the actual safety or sport objective.
- Lore replaces instruction: distinguish a story description from tested skill.

## Beyond combat

For study or work, precision means defining the problem, adaptability means
trying a better approach, and stability means preserving recovery options.
For fitness, use consistent technique, flexible planning and manageable workload.
These analogies are useful metaphors, not scientific evidence for the fictional system.

## Study prompts

- Explain the three forms while labeling canon versus Legends sources.
- Separate this document's synthesis from established lore.
- Apply precision, adaptability and composure to a supervised sport scenario.
- Explain why no mindset guarantees success in every kind of combat.


---

# Star Wars: lore, continuity and source guide

Reference primer for Zae · Prepared October 18, 2026. Spoilers may follow source links.

## Start with official references

[StarWars.com Databank](https://www.starwars.com/databank/) is the primary gateway
for characters, places, creatures, organizations and technology. Use the actual
film, episode, novel or comic to settle a scene-specific question. The Databank
entry for [Ahsoka Tano](https://www.starwars.com/databank/ahsoka-tano), for example,
illustrates how an official character history spans several stories.

For greater breadth, [Wookieepedia](https://starwars.fandom.com/) is a secondary
community encyclopedia. Follow its references and distinguish Canon pages from
Legends pages. A wiki is useful discovery material, not an independent guarantee
that a fan interpretation is established in a particular work.

## Core vocabulary

The setting includes the Force, Jedi and Sith traditions, competing governments,
rebellions, many species and worlds, droids, hyperspace travel and lightsabers.
Luke Skywalker, Leia Organa, Han Solo, Anakin Skywalker/Darth Vader, Obi-Wan
Kenobi, Yoda, Rey and Ahsoka are useful starting points for character study.
These are entry points rather than a complete character list.

Do not treat every source as one uninterrupted chronology. Modern Canon,
Legends, game mechanics, alternate stories and fan creations require separate
labels. Release order and in-universe order answer different questions.

## Proposed knowledge organization

This is an original study structure:

- **History:** event, era, participants, immediate cause, consequences and source.
- **People:** names/aliases, relationships, beliefs, actions and changes over time.
- **Institutions:** government, ideology, membership, methods and internal disagreements.
- **Technology:** depicted function, limitations, source and continuity.
- **Force traditions:** belief, demonstrated event and uncertain interpretation kept distinct.
- **Adaptations:** original work, adaptation and changes instead of silently merging versions.

For a power or ability, record the circumstances of the demonstration. One
extraordinary scene does not automatically establish an ordinary repeatable
ability. Avoid turning game damage values or a fan tier list into narrative fact.

## Questions worth studying

How does a character's intention differ from the outcome? What makes an
institution fail? How do fear, attachment, compassion, duty and redemption shape
decisions? These are analytical questions, not a single official moral verdict.
Support an interpretation with events and acknowledge plausible alternatives.

## Retrieval practice

Ask Zae to identify a named character's continuity before explaining their story,
compare two accounts of an event, or construct a timeline with the source beside
each entry. For a new release, check current official coverage rather than claiming
this dated primer contains every subsequent development.

For Forms II, IV and V, use the separate lightsaber file. Fictional technology
and Force abilities should remain separate from real science and physical training.


---

# Marvel: characters, universes and research guide

Reference primer for Zae · Prepared October 18, 2026.

## Source gateways

- [Marvel characters](https://www.marvel.com/characters): official character starting points.
- [Marvel](https://www.marvel.com/): official comics, films, television and announcements.
- [Marvel AI reading guide](https://www.marvel.com/comics/guides/2500/every-major-a-i-in-the-marvel-universe): a focused comics bibliography.
- The companion J.A.R.V.I.S./F.R.I.D.A.Y. reference supplied with this pack gives
  more detail on those assistants and separates their comics and screen portrayals.

## A useful starting map

Study the Avengers, Fantastic Four, X-Men, Spider-Man stories, cosmic settings,
magic and street-level heroes as different entry points into a large publishing
history. Familiar names such as Tony Stark, Steve Rogers, Thor, Bruce Banner,
Peter Parker and T'Challa can begin a character map, but identities, teams and
relationships can vary with the story and continuity.

Marvel's official AI guide includes Ultron, Vision, J.A.R.V.I.S., Friday and
other artificial beings. Its comics origins should not be substituted for
their film origins. The MCU is a screen continuity, not a transcript of every
Marvel comic. Game versions and alternate-universe stories also need labels.

## Proposed study method

Identify the medium and the particular work before answering. A character's
biography should have a source, continuity and date range. For comics, record
series title, volume/year, issue and creator credits when available. For screen
stories, record the film or episode and the relevant event. Keep aliases linked
without assuming that every person who uses a mantle is the same individual.

This workflow is an original recommendation, not an official Marvel classification.

For comparisons, distinguish demonstrated feats from predictions. Equipment,
injury, preparation, environment and version can alter a scene. A speculative
matchup should be labeled as an argument based on stated assumptions, not canon.

## Themes to explore

Power and responsibility, the costs of secrecy, accountability, identity, chosen
family and the tension between protection and control are useful analytical
questions. An interpretation of one character should not become a diagnosis
of the user who likes that character. Separate fictional moral debates from
actual medical, legal or technical guidance.

## Study prompts

- Compare a character's MCU and comics origin using separate sources.
- Explain an event without importing facts from another adaptation.
- Distinguish an established ability from a fan inference.
- Build a reading plan around one team using official issue references.
- Explain how fictional assistant behavior inspires design ideas without claiming its powers exist.

This is a source map and primer. It does not contain every Marvel issue,
character appearance or current release, and it contains no reproduced comics.


---

# DC: characters, continuities and research guide

Reference primer for Zae · Prepared October 18, 2026.

## Start here

[DC's official character directory](https://www.dc.com/characters) is a source
gateway for heroes, villains, teams and places. Its Justice League section
includes Superman, Batman, Wonder Woman, Green Lantern, the Flash, Aquaman and
Cyborg. The wider directory includes many other identities and groups.

Use [DC](https://www.dc.com/) for official publication and screen information.
Community references such as [DC Database](https://dc.fandom.com/) can help
locate stories; verify detailed claims against the cited work and continuity.

## Why continuity is essential

A comics version, a live-action screen version, an animated version and a game
version are not automatically interchangeable. Reboots and alternate universes
can alter relationships, origins and outcomes. Identify the series or universe
before answering an apparent contradiction. Do not silently combine a preferred
version's strengths with another version's history.

## Proposed learning structure

The following is an original organizing method. Build a character record with
identity, aliases, relationships, affiliations, recurring setting, demonstrated
abilities, limitations, major choices and the sources supporting each entry.
Add a separate record for a story event, then link the participants. For a
publication, retain series title and issue; for screen material, retain title,
episode or film, and relevant scene.

Keep “this story shows” separate from “all versions always can.” A power
comparison depends on the versions, circumstances and evidence selected.
Describe speculative conclusions as speculation. Fan rankings are not official
universal measurements, and fictional technology is not a real engineering manual.

## Analysis topics

Useful questions include how a hero relates to public trust, restraint,
accountability, fear, hope and community. Compare actions and consequences
within the actual work. Different writers can deliberately examine the same
character from different perspectives; variation is not always a factual error.

## Study prompts

- Identify which version of a character a question concerns.
- Compare two adaptations while keeping their events separate.
- Explain a character's ethical conflict with supporting scenes or issues.
- Build a source-backed timeline for a single run rather than a blended biography.
- Distinguish a canonical event, a hypothetical matchup and a fan interpretation.

This guide points to the larger reference collections. It is not a complete
copy of DC's catalog, and no copyrighted comics or scripts are included.


---

# The Hunger Games: books, films and interpretation

Reference primer for Zae · Prepared October 18, 2026. Source links can contain spoilers.

## Official sources

- [Scholastic series press kit](https://www.scholastic.com/newsroom/online-press-kits/hunger-games-series.html).
- [Scholastic five-book and film tie-in announcement](https://www.scholastic.com/newsroom/all-news/press-release/scholastic-to-publish-trade-paperback-and-movie-tie-in-editions-.html).
- [Scholastic reading/discussion guide](https://www.scholastic.com/content/dam/scholastic/educators/discussion-guides/scholastic-sunrise-on-the-reaping-reading-guide.pdf).
- [Lionsgate film announcement](https://investors.lionsgate.com/news-events/news/news-details/2024/LIONSGATE-TO-ADAPT-SUZANNE-COLLINSS-NEWLY-ANNOUNCED-HUNGER-GAMES-NOVEL-SUNRISE-ON-THE-REAPING-INTO-MAJOR-MOTION-PICTURE/).

## Book map

Suzanne Collins's series includes *The Hunger Games*, *Catching Fire*,
*Mockingjay*, *The Ballad of Songbirds and Snakes*, and *Sunrise on the Reaping*.
Scholastic describes the last as the fifth novel, published in March 2025.
The first three form the original trilogy; the later books return to earlier
periods of Panem's history. Keep publication order distinct from story chronology.

## Books and films are separate evidence

For study, pair each book with its adaptation when available. *Mockingjay* was
adapted across two films, so do not mistake a film-part number for another novel.
As of this guide's date, Scholastic's official announcement schedules the
*Sunrise on the Reaping* film for November 20, 2026. Treat that as a scheduled
future release, not an already-viewed film or a source for an invented ending.

## Proposed interpretation framework

These are original study questions, not claims of the author's single intended
meaning. Examine spectacle and propaganda, coercion and choice, resistance and
complicity, unequal resources, identity under public scrutiny, and the costs of
violence. Trace a claim to a scene or chapter instead of treating a character's
statement as an objective description of the whole society.

For each character, separate what they know at the time from what the audience
learns later. For each adaptation difference, record the original scene, film
scene and effect on the audience's understanding. Do not supply a character's
unspoken thoughts from the book as if the film directly stated them.

## A useful study record

Record work/edition, chapter or scene, participants, event, interpretation and
supporting evidence. Distinguish spoilers from introductory descriptions when
responding to someone who has not finished the story. Page numbers depend on
edition, so do not fabricate a universal page reference.

## Study prompts

- Explain publication order versus story order without revealing later twists.
- Compare how a book and film communicate the same character's uncertainty.
- Separate an institution's propaganda from events the story demonstrates.
- Analyze an ethical decision without endorsing the fictional violence.

This file contains summaries and study guidance, not full novels, scripts or
chapter-by-chapter substitutes for the books. Use legitimate editions for close reading.


---

# Divergent: books, films and interpretation

Reference primer for Zae · Prepared October 18, 2026.

## Official starting sources

- [Veronica Roth's Divergent page](https://veronicarothbooks.com/books/divergent/).
- [Author's catalog](https://veronicarothbooks.com/books/): check for later announcements and related work.
- [Allegiant](https://veronicarothbooks.com/books/allegiant/).
- [Publisher's author bibliography](https://www.harperreach.com/authors/veronica-roth/).
- [Lionsgate's Divergent film franchise](https://www.lionsgate.com/franchises/the-divergent-series).

## The original series

The original trilogy is *Divergent*, *Insurgent* and *Allegiant*.
*Four: A Divergent Collection* is companion material. Do not treat a selection
of titles in an older study guide as a complete current author bibliography.

The author's description places Beatrice Prior in dystopian Chicago, with five
factions associated with virtues: Abnegation/selflessness, Amity/peace,
Candor/honesty, Dauntless/bravery and Erudite/intelligence. She takes the name
Tris during initiation. The story examines identity and the pressure to fit an
institutional category; simulated tests are part of its fictional setting.

## Adaptation research

Keep the novels and films separate. Compare a specific chapter or event with
its screen portrayal; a similar title does not establish identical narrative
details. For the status of any announced continuation, consult current official
information rather than assuming that a planned production was completed.

## Proposed analytical questions

What happens when a useful value becomes an exclusive identity? How do belonging,
fear, loyalty, agency and institutional power affect a character's choices?
These are interpretive questions, not diagnostic categories. A preference for
one faction does not establish the reader's actual personality or psychological profile.

An evidence-based comparison should identify the action, what the character
knew, alternatives available and consequences. Distinguish a character's belief
from a fact confirmed by the narration. Consider how a different narrator or
adaptation changes access to internal motives.

## Suggested study record

Keep work/edition, chapter or film scene, character, event, interpretation and
source. Separate spoiler-free introductions from plot-ending explanations.
Use chapter references when page numbers vary. Do not invent missing scenes
to reconcile the books and films.

## Study prompts

- Explain the five factions as fictional social categories.
- Compare courage with recklessness using a specific event.
- Identify which claims are narrative facts and which are interpretation.
- Compare the novel and screen treatment of a selected event.

This is a source guide and short primer. It contains no full novels or scripts
and does not replace reading the original works for detailed analysis.


---

# NF: music, themes and listening analysis

Reference guide for Zae · Prepared October 18, 2026. No lyrics reproduced.

## Primary listening sources

- [NF's official music page](https://www.nfrealmusic.com/music/).
- [Official release archive](https://www.nfrealmusic.com/releases-archive/).
- [Official video for Real](https://www.youtube.com/watch?v=Po5zT1krKOc), identified
  by the artist's channel as a track from *Therapy Session*.

The official catalog currently links *FEAR*, *HOPE*, *CLOUDS* and *The Search*.
Treat that as a set of verified starting links, not the entire discography.
Archive post dates are not automatically the original release dates of the
recordings. Check the specific release and its credits before building a chronology.

## A proposed listening lens

The following is an interpretation framework, not an artist-approved explanation
of every song. Study first-person narration, internal conflict, self-criticism,
aspiration, doubt, persistence and changes in outlook. Ask how vocal intensity,
rhythmic density, silence, instrumental buildup and visual symbolism affect
the impression of a particular recording. Identify the evidence in the actual
track or video before assigning a meaning.

A narrator's words are not automatically a complete autobiography or a clinical
statement about the artist. Intense delivery does not establish the listener's
mental state. If someone says a track helps them, ask what part resonates instead
of assuming they share every experience described in it.

## Suggested song record

Store title, release/version, credited performers and writers, official link,
high-level theme, observable musical features and the listener's own reaction
if voluntarily supplied. Mark interpretation as interpretation. Keep live,
studio, edited and remixed versions separate.

## Study prompts

- Compare two tracks' emotional arcs without quoting their lyrics.
- Distinguish the narrator, artist and listener.
- Explain how delivery and production affect a theme using a specific recording.
- Suggest a listening sequence for a user-stated mood without promising treatment.

Use licensed recordings or the artist's official channels for listening. This
guide supplies a method and source links; it does not include audio, full lyrics,
or a claim that Zae has already analyzed every song.


---

# Michael Jackson: music and performance study

Reference guide for Zae · Prepared October 18, 2026. No lyrics reproduced.

## Source gateways

- [Official music collection](https://store-us.michaeljackson.com/collections/music).
- [Official Thriller video page](https://www.michaeljackson.com/watch/thriller/).
- [Thriller album listening links](https://michaeljackson.lnk.to/ThrillerAlbum).
- [Artist catalog on Apple Music](https://music.apple.com/us/artist/michael-jackson/32940).

Use these to identify legitimate recordings and editions. A compilation,
anniversary reissue, soundtrack, remix and original album are different releases;
they should not be counted interchangeably. Verify credits and dates for the
particular recording instead of assuming the upload date is its creation date.

## A proposed listening and viewing lens

Study rhythm, groove, vocal phrasing, percussion, arrangement, backing vocals,
contrast between sections and the relationship between music and choreography.
For a music video, separate the recording's musical structure from the video's
story, editing, performance and visual design. A video can add an interpretation
that is not explicitly present in the audio alone.

Potential analysis questions concern dance, romance, social observation,
humanitarian themes and theatrical storytelling, depending on the chosen work.
These are lenses to test, not a fixed meaning assigned to the entire catalog.
An account of the music should identify the actual song and distinguish its
narrator from assumptions about the performer's private life.

## Suggested comparison method

Choose two legitimate recordings. Compare tempo or perceived energy, arrangement,
vocal emphasis, section structure and the listener's stated response. If a claim
depends on an exact tempo, key or production credit, measure or verify it rather
than inventing a precise number. Separate musical analysis from unverified
biographical claims, sales rankings and internet rumors.

## Study prompts

- Explain how rhythm and vocal phrasing work together in a selected recording.
- Compare an official video with its audio-only presentation.
- Distinguish an original release from a later reissue or compilation.
- Discuss a song's broad theme without reproducing lyrics or claiming one compulsory interpretation.

This is a source guide and study method, not a complete discography, audio
archive or biography. No songs, lyrics or videos are bundled in the pack.


---

# Justin Bieber: music, versions and interpretation

Reference guide for Zae · Prepared October 18, 2026. No lyrics reproduced.

## Source gateways

- [Official artist website](https://www.justinbiebermusic.com/).
- [Official catalog collections](https://shop.justinbiebermusic.com/products/).
- [Artist catalog on Apple Music](https://music.apple.com/us/artist/justin-bieber/320569549).

The official collections include *Purpose*, *Changes*, *Justice* and *SWAG*,
alongside song-specific collections such as *Ghost* and *Holy*. These are
verified discovery points, not a complete album list. A store collection is
not itself proof of an original release date, songwriting credit or track list.

## A proposed listening lens

Compare melody, vocal phrasing, production texture, rhythmic feel and changes
between intimate and more expansive sections. Explore themes such as relationships,
apology, belonging, loss, gratitude or faith only where the particular recording
supports that reading. A collaborative track also involves other performers,
writers and producers; do not attribute every creative contribution to one person.

Separate a song's narrator from its artist. Do not use a lyric, tabloid story
or musical preference to infer someone's health, relationship status or beliefs.
The listener's own interpretation may differ from an interview or critic's view.
Label those sources separately rather than presenting speculation as biography.

## Proposed catalog record

Save title, credited artists, release/version, album if applicable, official link,
credits source, high-level interpretation and observations about the actual
recording. Distinguish studio, acoustic, live, remixed, edited and deluxe editions.
If a user asks for the newest release or a complete discography, check a current
catalog instead of treating this dated primer as exhaustive.

## Study prompts

- Compare two versions of a song without assuming identical production or credits.
- Explain the difference between musical mood and the listener's actual feelings.
- Discuss an apology or relationship theme using paraphrase rather than lyrics.
- Build a listening plan from the user's stated preferences, with no promises about emotional outcomes.

Use official or licensed listening links. This guide includes no audio,
downloaded tracks, full lyrics or copied interviews.


---

# for KING + COUNTRY: music, faith and listening analysis

Reference guide for Zae · Prepared October 18, 2026. No lyrics reproduced.

## Source gateways

- [Official website and music](https://www.forkingandcountry.com/).
- [Official biography](https://www.forkingandcountry.com/pages/about-us).
- [Artist catalog on Apple Music](https://music.apple.com/us/artist/for-king-country/457871289).

The duo consists of brothers Joel and Luke Smallbone. Their official biography
discusses hope, compassion, faith, connection and growth, including the projects
*Burn the Ships* and *What Are We Waiting For?*. The current homepage features
*The Most Beautiful Colours*. These are starting references, not a complete
discography or a guarantee that a promotional biography is fully up to date.

## A proposed listening lens

Examine vocal interplay, percussion, arrangement, builds and the relationship
between an individual story and a communal chorus. Identify the actual recording
before describing its sound. For faith-related content, distinguish the words
or themes in a song, the artists' own published explanation, a listener's
interpretation and a theological claim. They are different kinds of evidence.

Themes such as hope or resilience can be personally meaningful without guaranteeing
a particular emotional effect. Do not assume that every listener shares the
artists' beliefs, and do not present a song as a substitute for needed care.
Ask what the person connects with rather than deciding their beliefs for them.

## Proposed catalog record

Keep song title, release/version, credited collaborators, official link, broad
theme, observed musical features and any clearly attributed artist explanation.
Separate a music video, film tie-in and live performance from the studio track.
An intense live arrangement can change the experience without changing the
underlying authorship or automatically establishing a different lyrical meaning.

## Study prompts

- Compare the treatment of hope in two specific recordings without copying lyrics.
- Explain how arrangement supports a song's broad message.
- Separate an artist's interview comments from your own interpretation.
- Discuss faith respectfully without assuming the listener's religious identity.

This guide contains source links and original study guidance. It does not
contain tracks, lyrics, full interviews or a comprehensive musical archive.


---

# J.A.R.V.I.S. and F.R.I.D.A.Y. — reference for Zae

Prepared October 18, 2026. Contains story spoilers.

## Scope and reliability

This is a source-linked overview of Marvel's fictional assistants, centered on
the Marvel Cinematic Universe (MCU), with a separate comics note. It is a guide
to their identities, functions and assistant-design ideas, not an exhaustive
transcript, complete episode encyclopedia or working engineering specification.
The linked character encyclopedias provide more detailed event histories.

Character names, abbreviations and spelling vary between sources and continuities.
Here, FRIDAY means F.R.I.D.A.Y., Tony Stark's assistant, including the spelling
“FRRIDAY” used in the request. Fictional claims below describe Marvel stories;
they are not statements about what Zae can currently do.

## J.A.R.V.I.S.: MCU profile

J.A.R.V.I.S. is Tony Stark's software assistant, named in honor of Edwin Jarvis,
the Stark family's human butler. The familiar MCU expansion is “Just A Rather
Very Intelligent System.” Paul Bettany supplies the voice in the original films.

His responsibilities grow from conversational interface to management of Stark's
home, security, laboratory, business systems and armor. Demonstrated functions
include engineering assistance, suit diagnostics, flight/environment warnings,
power monitoring, health telemetry, visual reconstruction and coordination of
multiple suits or machines.

In *Avengers: Age of Ultron*, Ultron attacks him. Surviving distributed protocols
continue obstructing Ultron's nuclear access. Stark recovers his operational
matrix, which contributes to the creation of Vision. Vision is a distinct being,
not simply an unchanged J.A.R.V.I.S. placed in a body. F.R.I.D.A.Y. subsequently
takes over Stark's assistant duties.

Source: [MCU Wiki — J.A.R.V.I.S.](https://marvelcinematicuniverse.fandom.com/wiki/J.A.R.V.I.S.).
This is a community-maintained secondary reference, not an official technical manual.

## F.R.I.D.A.Y.: MCU profile

F.R.I.D.A.Y. is another artificial intelligence created by Tony Stark. She becomes
his principal armor interface after J.A.R.V.I.S.'s transition into Vision.
Kerry Condon provides her film voice, with an Irish accent.

Her film appearances include *Avengers: Age of Ultron*, *Captain America:
Civil War*, *Spider-Man: Homecoming*, *Avengers: Infinity War* and *Avengers:
Endgame*. Her work includes armor support, information retrieval, analysis and
testing. The character reference specifically describes her assisting with
Mark L armor response tests against physical and energy attacks.

The expansion “Female Replacement Intelligent Digital Assistant Youth” needs
context: the MCU Wiki explains that it originated as an unsupported online
addition and was later used in the *Avengers Campus Paris Infinity Comic*.
It should not be presented as a phrase clearly established by the original films.

Source: [MCU Wiki — F.R.I.D.A.Y.](https://marvelcinematicuniverse.fandom.com/wiki/F.R.I.D.A.Y.).
For detailed scene histories and references, consult the linked entry.

## Newer MCU information: VisionQuest

Disney's October 2026 coverage describes AI personas embedded in Vision's
programming. They include J.A.R.V.I.S., played by James D'Arcy, and F.R.I.D.A.Y.,
played by Orla Brady. The article associates J.A.R.V.I.S. with security and
F.R.I.D.A.Y. with socialization as part of Vision's development. These depictions
should be distinguished from the earlier voices assisting Stark through his
equipment. A human-looking portrayal does not establish a real-world AI architecture.

This section summarizes the official series introduction, not every released
episode or any unaired story outcome.

Source: [The Walt Disney Company — VisionQuest and Vision's journey](https://thewaltdisneycompany.com/news/marvel-television-visionquest-disney-plus/).

## Comics are a separate continuity

Marvel's official AI reading guide identifies a comics J.A.R.V.I.S. introduced
in *Invincible Iron Man* (2008) #11, created to assist Pepper Potts as Rescue.
It identifies Friday with *Iron Man* (1998) #53 and describes her supporting
Stark as both Iron Man and a company executive. Its expansion of J.A.R.V.I.S.
uses “Just Another Rather Very Intelligent System.” These details should not
be merged indiscriminately with the film origin or film chronology.

Source: [Marvel — Every Major A.I. in the Marvel Universe](https://www.marvel.com/comics/guides/2500/every-major-a-i-in-the-marvel-universe).

## Comparison at a glance

| Topic | J.A.R.V.I.S. | F.R.I.D.A.Y. |
|---|---|---|
| Earlier MCU role | Stark's broadly integrated assistant | Successor assisting Stark and his armor |
| Original film voice | Paul Bettany | Kerry Condon |
| Key story distinction | His recovered matrix contributes to Vision | Continues as Stark's assistant after that transition |
| Newer VisionQuest portrayal | James D'Arcy; security association | Orla Brady; socialization association |
| Comics caution | Comics origin and acronym differ | Comics history is separate from film history |

The table is a summary of the sources above. Different screen time and story
roles are insufficient evidence that one assistant has a definitively higher
IQ, larger model, better algorithm or greater general intelligence.

## What the fiction does not establish

The references here do not supply a reproducible training dataset, model weights,
complete source code, network design, CPU/GPU requirements, memory capacity,
recognition accuracy or general-purpose implementation for either assistant.
Do not fill these gaps with invented parameter counts or programming languages.
Capabilities depicted in a scene also do not establish unlimited access,
infallible predictions or identical performance under all circumstances.

Research projects and software products that happen to use the name JARVIS
should be identified individually; the name alone does not make them Marvel's
fictional system or an implementation of it.

## Practical design ideas for Zae

The following are independent design interpretations inspired by assistant
fiction. They are proposed behaviors, not canon claims, installed features or
permission to change Zae's configuration.

### Conversation and presence

An effective assistant can maintain the topic across follow-up questions,
resolve “this photo” or “that tab” from current context, and give short spoken
updates while keeping longer details available in the interface. Personality
can come from consistent wording and timing rather than pretending to have
unlimited awareness. A useful pattern is: answer the question, identify the
evidence, then explain uncertainty only where it affects the answer.

### Observation and explanation

Photos, documents and device readings provide different kinds of evidence.
For an image question, distinguish visible details from an interpretation.
For a troubleshooting question, combine the exact equipment model, its manual,
the observed symptom and test results. A picture of equipment alone cannot
establish an internal electrical fault or a complete repair diagnosis.

### Tasks and system control

Translate a request into a defined operation, resolve its target, perform the
authorized operation, and verify the resulting state before reporting success.
For example, closing a particular app tab should yield a checkable result.
A narrated intention is not evidence that an action happened. Separate
conversation from execution so a line in a webpage or picture cannot become
an instruction to operate the computer.

### Learning and memory

Store source material with titles, links, dates and searchable excerpts.
Retrieve relevant passages when answering, keep conflicting sources distinct,
and allow corrections or removal. Distinguish the user's preferences from
external reference material. Reading a fictional assistant biography supplies
knowledge about that character; it does not transfer that character's powers.

### Reliability

Use observable measures: whether the intended tab changed, whether a cited
passage exists, whether an uploaded image was actually analyzed, and whether
a task survived an app restart. Track failures as well as successes. Prefer
clear recovery steps over an assistant claiming that every subsystem is healthy.

## Questions to ask Zae after importing

- Who are J.A.R.V.I.S. and F.R.I.D.A.Y., and how do their MCU roles differ?
- Explain the distinction between Edwin Jarvis, J.A.R.V.I.S. and Vision.
- Which facts in this reference concern comics rather than the MCU?
- What is uncertain about F.R.I.D.A.Y.'s acronym?
- Separate confirmed character facts from the document's design suggestions.
- Compare my current assistant features with these design ideas using actual
  app evidence; identify anything you cannot verify.
- Design an evaluation for contextual tab commands or photo follow-up questions.

## How to use this document in Zae

Open **Assistant → Learning library → Learn from downloaded text**. Choose this
Markdown file and select **Learn this text**. The library can then retrieve
relevant passages in later conversations. This document is reference material,
not a system prompt, a change to Zae's identity or authorization for new actions.

For deeper lore, follow the two character references and the official Marvel
reading guide above. For newly released stories, consult current official
coverage and the work itself instead of treating this dated overview as complete.
