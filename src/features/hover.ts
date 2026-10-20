import * as vscode from 'vscode';

import { Runtime } from '../core/cache';
import { findSymbol, referenceAt, tagTokenIndex } from '../core/model';
import { SourceToken, statementAt, tokenAt, tokenIndex } from '../core/parser';
import { SnippetArg, SnippetEntry, plainTemplate } from '../core/snippets';

function formatArgument(argument: SnippetArg): string {
    const number = argument.optional ? `[${argument.num}]` : `(${argument.num})`;
    const kind = argument.kind ? `*${argument.kind}*` : '';
    if (kind && argument.description) return `- **${number}** ${kind} — ${argument.description}`;
    if (kind) return `- **${number}** ${kind}`;
    if (argument.description) return `- **${number}** ${argument.description}`;
    return `- **${number}**`;
}

function appendSnippet(markdown: vscode.MarkdownString, snippet: SnippetEntry): void {
    const syntax = snippet.templates.map(plainTemplate).join('\n');
    markdown.appendMarkdown('**Syntax**\n\n');
    markdown.appendCodeblock(syntax, 'suanpan');
    if (snippet.args.length > 0) {
        markdown.appendMarkdown('\n**Arguments**\n\n');
        markdown.appendMarkdown(snippet.args.map(formatArgument).join('\n'));
    }
}

function hoverForDefinition(
    markdown: vscode.MarkdownString,
    category: string,
    tag: number,
    model: ReturnType<Runtime['cache']['get']>
): void {
    const symbol = findSymbol(model, category, tag);
    if (!symbol) {
        markdown.appendMarkdown(`\n\n_${category} ${tag} is not defined in this file._`);
        return;
    }
    const type = symbol.typeName ? ` (\`${symbol.typeName}\`)` : '';
    markdown.appendMarkdown(
        `\n\n→ ${category} **${tag}**${type} — defined on line ${symbol.statement.line + 1}`
    );
}

/** Register the hover provider. */
export function registerHover(context: vscode.ExtensionContext, runtime: Runtime): void {
    const provider: vscode.HoverProvider = {
        provideHover(document, position) {
            const model = runtime.cache.get(document);
            const statement = statementAt(model.parsed, position.line);
            if (!statement) return undefined;

            const token = tokenAt(statement, position.line, position.character);
            if (!token) return undefined;
            const index = tokenIndex(statement, token);
            const values = statement.tokens.map(item => item.value);
            const command = runtime.database.findCommand(statement.verb);

            const markdown = new vscode.MarkdownString();
            markdown.supportHtml = false;
            markdown.isTrusted = false;

            // $variables inherit their value from the `variable` command.
            if (token.value.startsWith('$')) {
                const variable = model.variables.get(token.value.slice(1).toLowerCase());
                if (!variable) return undefined;
                markdown.appendMarkdown(
                    `**${variable.name}** — variable defined on line ${variable.statement.line + 1}\n\n`
                );
                markdown.appendCodeblock(variable.statement.text, 'suanpan');
                return new vscode.Hover(markdown, tokenRange(token));
            }

            if (index === 0) {
                if (!command) return undefined;
                const aliases = command.aliases.filter(alias => alias.toLowerCase() !== command.name.toLowerCase());
                markdown.appendMarkdown(`**${command.name}**`);
                if (aliases.length > 0) markdown.appendMarkdown(` (${aliases.join(', ')})`);
                if (command.summary) markdown.appendMarkdown(` — ${command.summary}`);
                markdown.appendMarkdown(`\n\nCategory: \`${command.category ?? 'control'}\``);

                const snippet = runtime.database.snippetFor(statement.verb, values);
                if (snippet) {
                    markdown.appendMarkdown('\n\n');
                    appendSnippet(markdown, snippet);
                }

                const types = runtime.database.typesFor(statement.verb);
                if (types.length > 0) {
                    const expected = runtime.database.typeTokenIndex(statement.verb);
                    if (!snippet) {
                        markdown.appendMarkdown('\n\n**Syntax**\n\n');
                        markdown.appendCodeblock(`${command.name} <Type> ...`, 'suanpan');
                    }
                    markdown.appendMarkdown(
                        `\n\nAccepts **${types.length}** ${command.category ?? 'object'} types` +
                            (expected !== undefined ? ` as argument ${expected + 1}.` : '.')
                    );
                }
                return new vscode.Hover(markdown, tokenRange(token));
            }

            const typeIndex = runtime.database.typeTokenIndex(statement.verb);
            if (index === typeIndex) {
                if (!command) return undefined;
                const type = runtime.database.findType(statement.verb, token.value);
                if (!type) return undefined;
                markdown.appendMarkdown(`**${type.name}**`);
                if (type.summary) markdown.appendMarkdown(` — ${type.summary}`);
                const aliases = (type.aliases ?? []).filter(alias => alias.toLowerCase() !== type.name.toLowerCase());
                if (aliases.length > 0) markdown.appendMarkdown(`\n\nAliases: ${aliases.map(a => `\`${a}\``).join(', ')}`);

                const snippet = runtime.database.snippetFor(statement.verb, values);
                if (snippet) {
                    markdown.appendMarkdown('\n\n');
                    appendSnippet(markdown, snippet);
                }
                return new vscode.Hover(markdown, tokenRange(token));
            }

            // A named section designation such as `section NZ2D 1000WB215`.
            if (statement.verb === 'section' && index === 2) {
                const snippet = runtime.database.snippetFor(statement.verb, values);
                if (!snippet) return undefined;
                markdown.appendMarkdown(`**${token.value}**`);
                if (snippet.summary) markdown.appendMarkdown(` — ${snippet.summary}`);
                markdown.appendMarkdown('\n\n');
                appendSnippet(markdown, snippet);
                return new vscode.Hover(markdown, tokenRange(token));
            }

            // A definition tag: `material Elastic1D 5` etc.
            const definitionIndex = tagTokenIndex(statement, runtime.database);
            if (index === definitionIndex && command?.category) {
                const type = statement.tokens[runtime.database.typeTokenIndex(statement.verb) ?? -1]?.value;
                markdown.appendMarkdown(
                    `**${command.category} ${token.value}**${type ? ` — \`${type}\`` : ''}`
                );
                markdown.appendMarkdown(`\n\nDefined on line ${statement.line + 1}.`);
                return new vscode.Hover(markdown, tokenRange(token));
            }

            const reference = referenceAt(statement, index, runtime.database);
            if (reference) {
                const argument = runtime.database.argumentFor(statement.verb, values, index);
                if (argument) markdown.appendMarkdown(`${formatArgument(argument)}\n`);
                hoverForDefinition(markdown, reference.category, reference.tag, model);
                return new vscode.Hover(markdown, tokenRange(token));
            }

            const argument = runtime.database.argumentFor(statement.verb, values, index);
            if (argument) {
                markdown.appendMarkdown(formatArgument(argument));
                return new vscode.Hover(markdown, tokenRange(token));
            }

            return undefined;
        },
    };

    context.subscriptions.push(
        vscode.languages.registerHoverProvider({ language: 'suanPan' }, provider)
    );
}

function tokenRange(token: SourceToken): vscode.Range {
    return new vscode.Range(token.line, token.start, token.endLine, token.end);
}
