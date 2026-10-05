# Examples of How Bitext Improves German Retrieval Results

The [aggregate benchmark](german-benchmark.md) shows that Approach 4 (the Bitext configuration) delivered the strongest overall German retrieval results. The following examples illustrate the practical differences. In every example, the ranks refer to the same passage that human evaluators marked as relevant.

The examples are divided into two groups: cases related to lemmatization and cases related to compound analysis.

## Group 1: Lemmatization Connects Different Forms of the Same Word

### Example 1: *Wiegen* – to Weigh

Consider the following query:

> **Wie viel wiegt die Große Anakonda?**
> *How much does the green anaconda weigh?*

The query uses **wiegt**, meaning “weighs.” The relevant passage instead uses the past-tense forms **wogen**, meaning “weighed,” and **wog**, also meaning “weighed”:

> **Männchen … wogen 2,5–14,3 kg … Das größte … Weibchen wog 97,5 kg.**
> *Males … weighed between 2.5 and 14.3 kg … The largest female weighed 97.5 kg.*

Although **wiegt**, **wogen**, and **wog** look quite different, they are all forms of the verb **wiegen**, meaning “to weigh.”

Approach 4 recognized that relationship and ranked the relevant passage **first**. Approaches 1, 2, and 3 missed the connection and ranked the same passage outside the top ten: Approach 1 ranked it 19th, Approach 2 ranked it 22nd, and Approach 3 ranked it 14th.

### Example 2: *Erfinden* – to Invent

> **Wer erfand das erste Teleskop?**
> *Who invented the first telescope?*

The query contains **erfand**, meaning “invented.” The relevant passage says:

> **Als erstes Teleskop gilt das Galilei-Fernrohr, 1608 erfunden …**
> *The Galilean telescope is considered the first telescope, invented in 1608 …*

The forms **erfand** and **erfunden** both come from **erfinden**, meaning “to invent.”

Approach 4 ranked the relevant passage third, within the top 10. Approaches 1, 2, and 3 missed the document: Approach 2 placed it 15th, Approach 3 placed it 31st, and Approach 1 did not return it within the top 100 results.

These examples illustrate an important advantage of lemmatization: users and documents do not need to use exactly the same grammatical form for the search engine to recognize that they are referring to the same action or concept.

## Group 2: Compound Analysis Uncovers Evidence Hidden Inside German Words

German frequently combines several concepts into a single compound word. This can make a relevant passage difficult to find when a user searches for the individual concepts separately.

### Example 3: Teacher Training

> **Wie lange dauert ein Studium in Deutschland, um Lehrer zu werden?**
> *How long does it take to complete a degree in Germany to become a teacher?*

The query uses **Studium**, meaning university studies or a degree course, and **Lehrer**, meaning teacher. The relevant passage expresses these ideas primarily through compounds:

> **Die Lehrerausbildung ist in Deutschland in zwei Phasen organisiert.**
> *Teacher training in Germany is organized in two phases.*

It also contains:

- **Lehrerausbildung** – teacher training
- **Lehrkräfte** – teachers or teaching staff
- **Lehramtsanwärter** – trainee teachers or teacher candidates
- **Studienseminare** – teacher-training institutes

Approach 4 exposed the useful concepts inside these compound words and ranked the relevant passage first. Approach 3, which also performs decompounding, ranked it 45th. Approaches 1 and 2 did not return it within the top 100.

### Example 4: Arabic Numerals

> **Wann entstanden die arabischen Zahlen?**
> *When did Arabic numerals originate?*

The query uses **Zahlen**, meaning numbers. The relevant passage uses the compound **Zahlzeichen**, meaning numeral symbols:

> **… die ursprünglich indischen zehn Zahlzeichen. Sie entstanden im 10. Jahrhundert …**
> *… the ten numeral symbols, originally from India. They originated in the 10th century …*

Approach 4 connected **Zahlen** – numbers – with the **Zahl** component inside **Zahlzeichen** – numeral symbols – and ranked the relevant passage fourth.

Approach 3 ranked it 18th, while Approaches 1 and 2 did not return it within the top 100.

## Key Takeaway

**Lemmatization** connects different grammatical forms, such as *wiegt*, *wogen*, and *wog*.

**Compound analysis** uncovers useful concepts inside words such as *Lehrerausbildung* and *Zahlzeichen*.

For users, the result is straightforward: relevant information appears closer to the top of the results, where it is more likely to be seen, selected, and passed to downstream systems such as rerankers, RAG applications, and AI agents.
