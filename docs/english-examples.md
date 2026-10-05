# Ten Real English Retrieval Examples

The [aggregate benchmark](english-benchmark.md) shows that the Bitext configuration delivered the strongest English top-10 results. The following examples make the practical differences easier to see. In every example, the ranks refer to the same passage marked relevant in the original MIRACL judgments.

## Example 1: Irregular Forms of *mean* in a Definition

**English query:** What is the meaning of public affairs?

> **Original English Passage:** Public Affairs Council. In the 1950s, the concept of corporate public affairs was only beginning to come into vogue, and at the time meant mostly legislature watching and corporate community involvement. Today, the definition of "public affairs" is much broader, encompassing political involvement, lobbying, corporate community involvement, issues management, grassroots advocacy, and public relations.

**The Language Issue.** The query asks for the **meaning** of a term, while the defining passage says what the term **meant**. The noun form and the irregular past-tense form belong to the same lexical family, but they do not share a suffix pattern that a light stemmer can reliably normalize.

**The Result.** Bitext ranks the judged-relevant passage at **position 5**. The Elasticsearch English analyzer does not return the same passage in the top 100.

**The How.** Bitext maps both **meaning** in the query and **meant** in the passage to the lemma **mean**. It also maps plural **affairs** to **affair** while retaining the original surface form. Elasticsearch obtains **mean** from the query's **meaning**, but does not obtain the same term from the passage's irregular **meant**.

## Example 2: Irregular Past Tense in Book-Sales Evidence

**English query:** How many copies did Salem's Lot sell?

> **Original English Passage:** 'Salem's Lot. In 2005, Centipede Press released a deluxe limited edition of "'Salem's Lot" with black and white photographs by Jerry Uelsmann and two short stories. The book was limited to 315 copies. An unsigned hardcover edition limited to 600 copies was later released. Both the signed and unsigned editions were sold out.

**The Language Issue.** The query uses the base verb **sell**, while the passage uses the irregular past form **sold**. It also repeats the plural noun **copies**. Suffix stemming does not reliably connect **sell** and **sold**.

**The Result.** Bitext ranks the judged-relevant passage at **position 1**. The Elasticsearch English analyzer ranks the same passage at **position 20**.

**The How.** Bitext maps **sold** in the passage to the lemma **sell** and maps **copies** to **copy** while preserving the original forms. The possessive in **Salem's** is normalized before lexical analysis, but the decisive additional query-to-passage link is the irregular **sell / sold** correspondence.

## Example 3: Irregular Participle *grown* Versus *grow*

**English query:** Can you grow tobacco in Tennessee?

> **Original English Passage:** Types of tobacco. Prior to the American Civil War, most tobacco grown in the US was fire-cured dark-leaf. In the United States, it is grown in northern middle Tennessee, western Kentucky and in Virginia. Fire-cured tobacco grown in Kentucky and Tennessee is used in some chewing tobaccos, moist snuff, some cigarettes and as a condiment leaf in pipe tobacco blends.

**The Language Issue.** The query uses the base verb **grow**, while the passage repeatedly uses the irregular past participle **grown**. Removing or modifying an ending cannot derive one form from the other.

**The Result.** Bitext ranks the judged-relevant passage at **position 3**. The Elasticsearch English analyzer ranks the same passage at **position 23**.

**The How.** Bitext maps every relevant occurrence of **grown** in the passage to the lemma **grow**, which appears directly in the query. The passage then provides the location evidence through repeated mentions of **Tennessee**. Elasticsearch passage analysis does not produce **grow** from **grown**.

## Example 4: Irregular Verb *build / built*

**English query:** When was the Berlin Wall built?

> **Original English Passage:** History of Berlin. On August 13, 1961 the Communist East German government started to build a wall, physically separating West Berlin from East Berlin and the rest of East Germany. The wall was built overnight with no warning.

**The Language Issue.** The query contains the irregular past-participle form **built**. The passage uses both the base form **build** and the participle **built**. A suffix-oriented stemmer leaves these as separate forms.

**The Result.** Bitext ranks the judged-relevant passage at **position 4**. The Elasticsearch English analyzer ranks the same passage at **position 16**.

**The How.** Bitext maps **built** to the dictionary lemma **build** while retaining the surface form. The query therefore matches both **started to build a wall** and **the wall was built**. Elasticsearch keeps **built** separate from **build**, so it cannot accumulate the same shared lexical evidence.

## Example 5: Irregular *made / make* Plus Noun Inflection

**English query:** What material are stents made out of?

> **Original English Passage:** Drug-eluting stent. The stent platform itself is an expandable framework, generally with an elaborate mesh-like design to allow expansion, flexibility, and in some cases the ability to make/enlarge side openings for side vessels. As of 2009, materials that had been explored included magnesium, polylactic acid, polycarbonate polymers, and salicylic acid polymers.

**The Language Issue.** The query uses **made**, while the passage uses **make** in **make/enlarge**. It also alternates between singular and plural forms such as **stent / stents** and **material / materials**. The irregular verb pair is not recoverable through suffix stripping.

**The Result.** Bitext ranks the judged-relevant passage at **position 6**. The Elasticsearch English analyzer ranks the same passage at **position 22**.

**The How.** Bitext maps **made** to **make**, **stents** to **stent**, and **materials** to **material**, while retaining the original surface terms. This gives the query direct lexical links to **make/enlarge**, the repeated mentions of **stents**, and the sentence listing the materials explored.

## Example 6: Avoiding Over-Stemming of *majority*

**English query:** What is the majority race in California?

> **Original English Passage:** Race and ethnicity in the United States. White Americans are the majority in 49 of the 50 states, with Hawaii as the exception. Non-Hispanic Whites are the majority in 46 states; Hawaii, New Mexico, California, and Texas are the exceptions. These five jurisdictions have minority majorities.

**The Language Issue.** The word **majority** is a complete lexical item with a meaning distinct from **major**. Elasticsearch's English stemmer reduces **majority** to the stem **major**, discarding the exact term even though the query and passage use it repeatedly.

**The Result.** Bitext ranks the judged-relevant passage at **position 3**. The Elasticsearch English analyzer ranks the same passage at **position 23**.

**The How.** Bitext preserves **majority** as the searchable term in both the query and passage, while Elasticsearch represents it as **major**. That keeps the exact lexical item separate from the broader word **major** instead of forcing both into one stem.

## Example 7: Contextual Preservation of a Television-Series Title

**English query:** How long has Days of Our Lives been on?

> **Original English Passage:** Days of Our Lives. Days of Our Lives is an American daytime soap opera broadcast on the NBC television network. It is one of the longest-running scripted television programs in the world, airing nearly every weekday since November 8, 1965.

**The Language Issue.** The title **Days of Our Lives** is made from ordinary English words whose lowercase forms are morphologically analyzable. In this context, however, **Days** and **Lives** are components of a named work. Generic stemming reduces them to **dai** and **live**, losing the specific title surfaces.

**The Result.** Bitext ranks the judged-relevant passage at **position 2**. The Elasticsearch English analyzer ranks the same passage at **position 24**.

**The How.** The sentence-aware Bitext analyzer preserves the title terms **Days** and **Lives** in the query's entity context. Elasticsearch emits the stems **dai** and **live**. The passage repeats the exact series title and states that it has aired nearly every weekday since November 8, 1965.

## Example 8: Preserving a Policy Name Instead of Collapsing It to a Stem

**English query:** When was Ukrainization policy first implemented in the Ukraine?

> **Original English Passage:** Ukrainization. Until the early-1930s, Ukrainian culture enjoyed a widespread revival due to Bolshevik policies known as the policy of Korenization. In these years a Ukrainization program was implemented throughout the republic.

**The Language Issue.** The query distinguishes the policy name **Ukrainization** from the country **Ukraine**. Elasticsearch's stemmer reduces both to **ukrain**, also collapsing related nationality forms. That removes a useful distinction between the thing being asked about and its geographical context.

**The Result.** Bitext ranks the judged-relevant passage at **position 5**. The Elasticsearch English analyzer ranks the same passage at **position 22**.

**The How.** Bitext preserves the exact term **Ukrainization** and keeps it distinct from the query's **Ukraine**, whereas Elasticsearch reduces both to **ukrain**. Bitext also maps **implemented** to the lemma **implement**.

## Example 9: Irregular *come / came* and Preservation of Religion Names

**English query:** Does Christianity come from Judaism?

> **Original English Passage:** Origins of Judaism. For centuries, the traditional understanding has been that Judaism came before Christianity and that Christianity separated from Judaism some time after the destruction of the Second Temple in 70 CE.

**The Language Issue.** The query uses **come**, while the passage uses the irregular past form **came**. At the same time, **Christianity** is the name of a religion, not merely the adjective or noun **Christian**. Elasticsearch stems **Christianity** to **christian** and does not connect **came** to **come**.

**The Result.** Bitext ranks the judged-relevant passage at **position 6**. The Elasticsearch English analyzer ranks the same passage at **position 38**.

**The How.** Bitext maps **came** in the passage and **come** in the query to the shared lemma **come**, while preserving **Christianity** and **Judaism** as complete lexical terms. The passage directly discusses the traditional view that Judaism came before Christianity.

## Example 10: Possessive Normalization Without Stemming a Proper Name

**English query:** When was Disney's animated Cinderella first released?

> **Original English Passage:** Cinderella (1950 film). Cinderella is a 1950 American animated musical fantasy film produced by Walt Disney and originally released by RKO Radio Pictures. Based on the fairy tale "Cinderella" by Charles Perrault, it is the twelfth Disney animated feature film.

**The Language Issue.** The possessive ending in **Disney's** must be removed before lexical and entity lookup, but the proper name itself should remain intact. The query and passage also use inflected verb forms such as **animated** and **released**. Elasticsearch handles the possessive but then Porter-stems the name and verbs to **disnei**, **anim**, and **releas**.

**The Result.** Bitext ranks the judged-relevant passage at **position 3**. The Elasticsearch English analyzer ranks the same passage at **position 14**.

**The How.** Bitext first normalizes **Disney's** to **Disney**, then preserves the proper name rather than stemming it. It retains the surface forms **animated** and **released** while adding the lemmas **animate** and **release**. The ranking gain is best understood as cumulative precise lexical evidence, not possessive stripping alone.
