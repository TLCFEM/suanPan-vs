import * as vscode from 'vscode';

import { Runtime } from '../core/cache';
import { findSymbol, referenceAt, tagTokenIndex } from '../core/model';
import { statementAt, tokenAt, tokenIndex } from '../core/parser';

/** Register go-to-definition for tags and variables. */
export function registerDefinition(context: vscode.ExtensionContext, runtime: Runtime): void {
    const provider: vscode.DefinitionProvider = {
        provideDefinition(document, position) {
            const model = runtime.cache.get(document);
            const statement = statementAt(model.parsed, position.line);
            if (!statement) return undefined;

            const token = tokenAt(statement, position.line, position.character);
            if (!token) return undefined;

            if (token.value.startsWith('$')) {
                const variable = model.variables.get(token.value.slice(1).toLowerCase());
                if (!variable) return undefined;
                return new vscode.Location(
                    document.uri,
                    new vscode.Range(variable.token.line, variable.token.start, variable.token.endLine, variable.token.end)
                );
            }

            const index = tokenIndex(statement, token);
            if (index === tagTokenIndex(statement, runtime.database)) return undefined;

            const reference = referenceAt(statement, index, runtime.database);
            if (!reference) return undefined;

            const symbol = findSymbol(model, reference.category, reference.tag);
            if (!symbol) return undefined;
            return new vscode.Location(
                document.uri,
                new vscode.Range(symbol.token.line, symbol.token.start, symbol.token.endLine, symbol.token.end)
            );
        },
    };

    context.subscriptions.push(
        vscode.languages.registerDefinitionProvider({ language: 'suanPan' }, provider)
    );
}
