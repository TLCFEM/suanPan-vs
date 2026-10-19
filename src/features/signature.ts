import * as vscode from 'vscode';

import { Runtime } from '../core/cache';
import { statementAt } from '../core/parser';
import { SnippetEntry, SnippetArg, plainTemplate } from '../core/snippets';

function pickTemplate(snippet: SnippetEntry, values: string[]): string {
    const lower = values.map(value => value.toLowerCase());
    return (
        snippet.templates.find(template => {
            const words = template.toLowerCase().split(/\s+/);
            return words[0] === lower[0] && (words[1] ?? '') === (lower[1] ?? '');
        }) ?? snippet.templates[0]
    );
}

function parameterLabel(argument: SnippetArg): string {
    const number = argument.optional ? `[${argument.num}]` : `(${argument.num})`;
    return argument.kind ? `${number} ${argument.kind}` : number;
}

/** Register signature help for command arguments. */
export function registerSignatureHelp(context: vscode.ExtensionContext, runtime: Runtime): void {
    const provider: vscode.SignatureHelpProvider = {
        provideSignatureHelp(document, position) {
            const model = runtime.cache.get(document);
            const statement = statementAt(model.parsed, position.line);
            if (!statement) return undefined;

            const values = statement.tokens.map(token => token.value);
            const snippet = runtime.database.snippetFor(statement.verb, values);
            if (!snippet || snippet.args.length === 0) return undefined;

            const before = statement.tokens.filter(
                token =>
                    token.line < position.line ||
                    (token.line === position.line && token.start < position.character)
            );
            const index = before.length;

            const typeIndex = runtime.database.typeTokenIndex(statement.verb) ?? 0;
            if (index <= typeIndex) return undefined;

            let active = snippet.args.findIndex(argument => argument.tokenIndex === index);
            if (active < 0) {
                for (let i = 0; i < snippet.args.length; i++) {
                    if (snippet.args[i].tokenIndex <= index) active = i;
                }
            }
            if (active < 0) active = 0;

            const signature = new vscode.SignatureInformation(
                plainTemplate(pickTemplate(snippet, values)),
                new vscode.MarkdownString(snippet.summary)
            );
            signature.parameters = snippet.args.map(argument => {
                const detail = [argument.kind, argument.description].filter(Boolean).join(', ');
                return new vscode.ParameterInformation(parameterLabel(argument), detail);
            });
            signature.activeParameter = active;

            const help = new vscode.SignatureHelp();
            help.signatures = [signature];
            help.activeSignature = 0;
            help.activeParameter = active;
            return help;
        },
    };

    context.subscriptions.push(
        vscode.languages.registerSignatureHelpProvider(
            { language: 'suanPan' },
            provider,
            ' ',
            ','
        )
    );
}
