import * as vscode from 'vscode';

import { Runtime } from '../core/cache';
import { symbolsOf } from '../core/model';
import { Statement, statementAt } from '../core/parser';
import { SnippetEntry, plainTemplate } from '../core/snippets';

interface Context {
    verb: string;
    /** Index of the token being completed (or the next token index). */
    index: number;
    /** Already typed characters of the token being completed. */
    partial: string;
    values: string[];
    range: vscode.Range;
}

function resolveContext(document: vscode.TextDocument, statement: Statement | undefined, position: vscode.Position): Context {
    const tokens = statement?.tokens.filter(
        token =>
            token.line < position.line ||
            (token.line === position.line && token.start < position.character)
    ) ?? [];

    const inside = tokens.length > 0 ? tokens[tokens.length - 1] : undefined;
    const insideToken =
        inside !== undefined &&
        inside.endLine === position.line &&
        position.character > inside.start &&
        position.character <= inside.end;

    const index = insideToken ? tokens.length - 1 : tokens.length;
    const partial = insideToken && inside ? inside.value.slice(0, position.character - inside.start) : '';
    const values = tokens.map(token => token.value);

    let range: vscode.Range;
    if (insideToken && inside) {
        range = new vscode.Range(inside.line, inside.start, inside.endLine, inside.end);
    } else {
        const word = document.getWordRangeAtPosition(position, /[^\s,!#]+/);
        range = word ?? new vscode.Range(position, position);
    }

    return {
        verb: (values[0] ?? '').toLowerCase(),
        index,
        partial,
        values,
        range,
    };
}

function markdownForSnippet(snippet: SnippetEntry | undefined): vscode.MarkdownString | undefined {
    if (!snippet) return undefined;
    const markdown = new vscode.MarkdownString();
    if (snippet.summary) markdown.appendMarkdown(`${snippet.summary}\n\n`);
    markdown.appendCodeblock(snippet.templates.map(plainTemplate).join('\n'), 'suanpan');
    return markdown;
}

function tailOfTemplate(snippet: SnippetEntry | undefined, keyword: string): string | undefined {
    if (!snippet) return undefined;
    const template = snippet.templates.find(line => {
        const tokens = line.split(/\s+/);
        return tokens.some(token => token.toLowerCase() === keyword.toLowerCase());
    }) ?? snippet.templates[0];
    if (!template) return undefined;
    const index = template.toLowerCase().indexOf(keyword.toLowerCase());
    if (index < 0) return undefined;
    return template.slice(index + keyword.length);
}

/** Register context aware completion. */
export function registerCompletion(context: vscode.ExtensionContext, runtime: Runtime): void {
    const provider: vscode.CompletionItemProvider = {
        provideCompletionItems(document, position) {
            const prefix = document.lineAt(position.line).text.slice(0, position.character);
            if (prefix.includes('!') || /^\s*#/.test(prefix)) return undefined;

            const model = runtime.cache.get(document);
            const statement = statementAt(model.parsed, position.line);
            const current = resolveContext(document, statement, position);
            const database = runtime.database;

            const items: vscode.CompletionItem[] = [];

            if (current.index === 0) {
                for (const name of database.commandNames()) {
                    const command = database.findCommand(name);
                    if (!command) continue;
                    const canonical = name.toLowerCase() === command.name.toLowerCase();
                    const item = new vscode.CompletionItem(name, vscode.CompletionItemKind.Keyword);
                    item.range = current.range;
                    item.detail = canonical
                        ? command.summary || command.category || 'command'
                        : `alias of ${command.name}`;
                    item.documentation = markdownForSnippet(database.snippetFor(name, [name]));
                    const snippet = database.snippetFor(name, [name]);
                    if (snippet?.templates[0]?.toLowerCase().startsWith(name.toLowerCase())) {
                        item.insertText = new vscode.SnippetString(snippet.templates[0]);
                    }
                    item.sortText = `${canonical ? '0' : '1'}${name.toLowerCase()}`;
                    items.push(item);
                }
                return new vscode.CompletionList(items, false);
            }

            const command = database.findCommand(current.verb);
            const typeIndex = database.typeTokenIndex(current.verb);

            // `section NZ2D <designation>` and friends use named designations.
            if (current.verb === 'section' && current.index === 2) {
                const container = current.values[1];
                const seen = new Set<string>();
                for (const entry of database.designationsFor(container)) {
                    if (!entry.prefix || seen.has(entry.prefix.toLowerCase())) continue;
                    seen.add(entry.prefix.toLowerCase());
                    const tail = tailOfTemplate(entry, entry.prefix);
                    const item = new vscode.CompletionItem(entry.prefix, vscode.CompletionItemKind.Constant);
                    item.range = current.range;
                    item.detail = entry.summary;
                    item.documentation = markdownForSnippet(entry);
                    if (tail) item.insertText = new vscode.SnippetString(entry.prefix + tail);
                    item.sortText = `0${entry.prefix.toLowerCase()}`;
                    items.push(item);
                }
                if (items.length > 0) return new vscode.CompletionList(items, false);
            }

            // The type/property keyword.
            const types = database.typesFor(current.verb);
            if (typeIndex !== undefined && current.index === typeIndex && types.length > 0) {
                for (const type of types) {
                    const snippet = database.snippetFor(current.verb, [...current.values.slice(0, typeIndex), type.name]);
                    const tail = tailOfTemplate(snippet, type.name);
                    const item = new vscode.CompletionItem(type.name, vscode.CompletionItemKind.TypeParameter);
                    item.range = current.range;
                    item.detail = type.summary || command?.category;
                    item.documentation = markdownForSnippet(snippet);
                    item.insertText = tail ? new vscode.SnippetString(type.name + tail) : type.name;
                    item.sortText = `0${type.name.toLowerCase()}`;
                    items.push(item);
                }
                return new vscode.CompletionList(items, false);
            }

            // Arguments: offer known tags (and boolean values) based on the
            // argument documentation of the active type.
            const values = [...current.values];
            if (current.index >= values.length) values.push('');
            const argument = database.argumentFor(current.verb, values, current.index);

            if (argument) {
                if (/bool/i.test(argument.kind)) {
                    for (const value of ['true', 'false', 'on', 'off', 'yes', 'no', '1', '0']) {
                        const item = new vscode.CompletionItem(value, vscode.CompletionItemKind.Value);
                        item.range = current.range;
                        item.detail = argument.description;
                        items.push(item);
                    }
                }

                const description = argument.description.toLowerCase();
                const categories: Array<[RegExp, string]> = [
                    [/\bmaterial tag\b/, 'material'],
                    [/\bsection tag\b/, 'section'],
                    [/\bnode i\b|\bnode j\b|\bnode tag\b|\bnodes?\b/, 'node'],
                    [/\belement tag\b|\belements?\b/, 'element'],
                    [/\bamplitude tag\b/, 'amplitude'],
                    [/\bgroup tag\b/, 'group'],
                    [/\bstep tag\b/, 'step'],
                ];
                for (const [pattern, category] of categories) {
                    if (!pattern.test(description)) continue;
                    for (const symbol of symbolsOf(model, category)) {
                        const item = new vscode.CompletionItem(
                            String(symbol.tag),
                            vscode.CompletionItemKind.Reference
                        );
                        item.range = current.range;
                        item.detail = symbol.typeName ? `${category} ${symbol.typeName}` : category;
                        item.documentation = new vscode.MarkdownString(
                            `\`${symbol.statement.text}\``
                        );
                        item.sortText = `0${String(symbol.tag).padStart(8, '0')}`;
                        items.push(item);
                    }
                    break;
                }
            }

            // Variables can be used anywhere.
            for (const variable of model.variables.values()) {
                const item = new vscode.CompletionItem(`$${variable.name}`, vscode.CompletionItemKind.Variable);
                item.range = current.range;
                item.detail = 'variable';
                item.documentation = new vscode.MarkdownString(`\`${variable.statement.text}\``);
                item.sortText = `1${variable.name.toLowerCase()}`;
                items.push(item);
            }

            return new vscode.CompletionList(items, false);
        },
    };

    context.subscriptions.push(
        vscode.languages.registerCompletionItemProvider({ language: 'suanPan' }, provider, ' ', ',')
    );
}
