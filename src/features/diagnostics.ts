import * as vscode from 'vscode';

import { Runtime } from '../core/cache';
import { findSymbol, referenceAt } from '../core/model';
import { warnToken } from './util';

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
                diagnostics.push(warnToken(token, `Unknown command "${token.value}".`));
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
                    diagnostics.push(
                        warnToken(
                            token,
                            `Unknown ${command.category ?? 'object'} type "${token.value}".`,
                            `suanPan ${runtime.database.version}`
                        )
                    );
                }
            }

            // Coded sections (`EU2D`, `US2DA`, ...) accept only the
            // designations listed in the C++ tables. A misspelled container is
            // already reported as an unknown type above.
            const containerType =
                statement.verb === 'section' && statement.tokens.length > 2
                    ? runtime.database.findType('section', statement.tokens[1].value)
                    : undefined;
            if (unknownType && containerType) {
                const container = statement.tokens[1].value;
                const designation = statement.tokens[2];
                const names = runtime.database.designationNamesFor(container);
                if (
                    names.length > 0 &&
                    !designation.value.startsWith('$') &&
                    !names.some(name => name.toLowerCase() === designation.value.toLowerCase())
                ) {
                    diagnostics.push(
                        warnToken(
                            designation,
                            `Unknown ${container} section designation "${designation.value}".`,
                            `suanPan ${runtime.database.version}`
                        )
                    );
                }
            }

            if (unknownReference) {
                for (let index = 1; index < statement.tokens.length; index++) {
                    const reference = referenceAt(statement, index, runtime.database);
                    if (!reference) continue;
                    if (findSymbol(model, reference.category, reference.tag)) continue;
                    diagnostics.push(
                        warnToken(
                            reference.token,
                            `Undefined ${reference.category} ${reference.tag}.`
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
