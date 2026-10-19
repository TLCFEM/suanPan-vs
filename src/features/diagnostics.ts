import * as vscode from 'vscode';

import { Runtime } from '../core/cache';
import { findSymbol, referenceAt } from '../core/model';

/** Register model diagnostics. */
export function registerDiagnostics(context: vscode.ExtensionContext, runtime: Runtime): void {
    const collection = vscode.languages.createDiagnosticCollection('suanPan');
    context.subscriptions.push(collection);

    const refresh = (document: vscode.TextDocument) => {
        const configuration = vscode.workspace.getConfiguration('suanpan');
        if (!configuration.get<boolean>('diagnostics.enable', true)) {
            collection.delete(document.uri);
            return;
        }

        const unknownType = configuration.get<boolean>('diagnostics.unknownType', true);
        const unknownReference = configuration.get<boolean>('diagnostics.unknownReference', false);

        const model = runtime.cache.get(document);
        const diagnostics: vscode.Diagnostic[] = [];

        if (model.parsed.danglingContinuation !== undefined) {
            const line = model.parsed.danglingContinuation;
            diagnostics.push(
                new vscode.Diagnostic(
                    new vscode.Range(line, 0, line, model.parsed.lines[line]?.length ?? 0),
                    'Line continuation with `\\` reaches the end of the file.',
                    vscode.DiagnosticSeverity.Warning
                )
            );
        }

        for (const statement of model.parsed.statements) {
            const command = runtime.database.findCommand(statement.verb);

            if (!command && /^[a-z]/i.test(statement.verb)) {
                const token = statement.tokens[0];
                diagnostics.push(
                    new vscode.Diagnostic(
                        new vscode.Range(token.line, token.start, token.endLine, token.end),
                        `Unknown command "${token.value}".`,
                        vscode.DiagnosticSeverity.Warning
                    )
                );
                continue;
            }

            if (!command) continue;

            const typeIndex = runtime.database.typeTokenIndex(statement.verb);
            if (typeIndex !== undefined && runtime.database.typesFor(statement.verb).length > 0) {
                const token = statement.tokens[typeIndex];
                if (
                    unknownType &&
                    token &&
                    !token.value.startsWith('$') &&
                    !runtime.database.findType(statement.verb, token.value)
                ) {
                    const diagnostic = new vscode.Diagnostic(
                        new vscode.Range(token.line, token.start, token.endLine, token.end),
                        `Unknown ${command.category ?? 'object'} type "${token.value}".`,
                        vscode.DiagnosticSeverity.Warning
                    );
                    diagnostic.source = `suanPan ${runtime.database.version}`;
                    diagnostics.push(diagnostic);
                }
            }

            if (unknownReference) {
                for (let index = 1; index < statement.tokens.length; index++) {
                    const reference = referenceAt(statement, index, runtime.database);
                    if (!reference) continue;
                    if (findSymbol(model, reference.category, reference.tag)) continue;
                    diagnostics.push(
                        new vscode.Diagnostic(
                            new vscode.Range(
                                reference.token.line,
                                reference.token.start,
                                reference.token.endLine,
                                reference.token.end
                            ),
                            `Undefined ${reference.category} ${reference.tag}.`,
                            vscode.DiagnosticSeverity.Warning
                        )
                    );
                }
            }
        }

        collection.set(document.uri, diagnostics);
    };

    if (vscode.window.activeTextEditor?.document.languageId === 'suanPan') {
        refresh(vscode.window.activeTextEditor.document);
    }

    context.subscriptions.push(
        vscode.workspace.onDidOpenTextDocument(document => {
            if (document.languageId === 'suanPan') refresh(document);
        }),
        vscode.workspace.onDidChangeTextDocument(event => {
            if (event.document.languageId === 'suanPan') refresh(event.document);
        }),
        vscode.workspace.onDidCloseTextDocument(document => collection.delete(document.uri))
    );
}
