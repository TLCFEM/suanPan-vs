import * as vscode from 'vscode';

import { SourceToken, Statement } from '../core/parser';

/** Editor range covering a token, including continuation lines. */
export function tokenRange(token: SourceToken): vscode.Range {
    return new vscode.Range(token.line, token.start, token.endLine, token.end);
}

/** Tokens of a statement that end before the cursor position. */
export function tokensBefore(statement: Statement | undefined, position: vscode.Position): SourceToken[] {
    return statement?.tokens.filter(
        token =>
            token.line < position.line ||
            (token.line === position.line && token.start < position.character)
    ) ?? [];
}

/** A warning diagnostic anchored on a token. */
export function warnToken(token: SourceToken, message: string, source?: string): vscode.Diagnostic {
    const diagnostic = new vscode.Diagnostic(
        tokenRange(token),
        message,
        vscode.DiagnosticSeverity.Warning
    );
    if (source) diagnostic.source = source;
    return diagnostic;
}
