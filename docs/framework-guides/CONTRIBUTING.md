# Contributing to Port's documentation

Here you can find resources and guidelines on how to contribute to Port's documentation and how to correctly write and fix documentation articles.

## Get involved

The best way to suggest edits for an existing page is by using the "Edit this page" button at the bottom of most docs, this button will take you to the GitHub interface to make and propose changes.

If you want to add a new documentation page, please fork the repository and after adding the new docs, create a PR which will be reviewed by our team.

Contributions are very welcome. If you think you need help planning your contribution, please ping us on Twitter at [@tweetsbyport](https://mobile.twitter.com/tweetsbyport) or by opening an issue or PR targeting this repository and let us know you are looking for a bit of help.

## Styling guidelines

### Capital letters

1. **Headlines** - All titles should look the same throughout the whole document. Please make sure that capital letters in headlines adhere to the following rules
   1. **Section headlines (H1)** - capital letters throughout the headlines (including propositions). For example, "Port Platform Overview".
   2. **Subtitles (H2-4)** - capital letters only for the first word of the subtitle. The rest of the sentence will be in lowercase letters. For example: "Our building-space".
   3. **Notice/tip/info boxes** - All letters will be capital letters.
   4. **Other** - discuss the matter with the rest of the team and decide together.
2. **Links** - unless the link is at a start of a new sentence, it should not be with capital letters.
3. **General product names** - well known products such as Lambda, Kubernetes, Argo CD, etc. should follow their standard capitalization rules and styling.
4. **Button names** - will be capitalized according to the exact way the term is written in Port.
5. **After brackets or a colon (`:`)** - there is no need to put a capital letter.

### Punctuation

1. Every sentence must end with a period, including the sentences in tip/notice boxes.
2. Before an image/code line example is displayed, put a colon (`:`).
3. Lists: a short list (any list in which each line is less than 2 sentences) should appear as shown below. The mark `;`, at the end of each line, and a period at the last line.
   1. One;
   2. Two;
   3. Three.

### Writing style

1. Pay attention to writing "the … **will** look like this", instead of "the … **should** look like this". It shows more confidence.
2. Write the docs in second person grammar, and not in third person grammar. For example: "**you** should do this" instead of "**we** will do this".
3. Write small numbers (up to 10), in a word and not in a number. For example **two** instead of **2**.
4. Make sure the spacing between different types of lines is the same throughout the whole document.
5. When referring to someone performing an action that isn’t the docs reader, refer to them in a plural word, and not in second body grammer. For example, “they can use”, instead of “he can use”.
6. Try avoiding adding “ing” to actions. For example, “reacting to” compared to “react to”.

### Code examples and snippets

1. Try to make use of existing code examples to write new ones, they already list and implement most of the basic helper functions so they can save you time and keep a consistent code format.
2. When naming blueprints, entities and relations use the following guidelines:
   1. Blueprint identifiers: should use camelCase styling with the first letter of a phrase always being a lower letter, for example: `microservice`, `deploymentConfig`, `servicePod`, etc.
   2. Blueprint titles: should use the section headlines (H1) rules: capital letters throughout the headlines.
   3. Blueprint properties: should use camelCase styling with the first letter of a property always being a lower letter, for example: `url`, `eventType`, `dashboardLink`, etc.
   4. Entity identifiers: should use kebab-case styling with letters always being lower, for example: `notification-service`, `recommendation-service`, `authentication`, etc.
   5. Entity titles: Should use the section headlines (H1) rules: capital letters throughout the headlines.
   6. Relation identifiers: should follow the name of the matching target blueprint, for example: a relation from microservice to package should use the `package` identifier, because that is the identifier of the `package` blueprint.
   7. Relation titles: should usually follow the title of the matching target blueprint.
   8. Self-service action identifiers: should use snake_case styling with letters always being lower, for example: `add_secret`, `create_bucket`, etc.
   9. Self-service action user inputs: should use camelCase styling with the first letter of an input always being a lower letter, for example: `url`, `serviceName`, `templateUrl`, etc.

## Contributor License Agreement (CLA)

In order to accept your pull request, we need you to submit a CLA. You only need to do this once, so if you've already contributed to Port's documentation before, you're good to go. If you are submitting a pull request for the first time, just let us know that you have completed the CLA and we can cross-check with your GitHub username.

The CLA template is available [here](./contributor-license-agreement.txt), please fill it according to the instructions and then email the filled agreement to [support@getport.io](mailto:support@getport.io).
