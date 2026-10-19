import * as vscode from 'vscode';

/**
 * A token of a suanPan model file with its position in the document.
 */
export interface Token {
	text: string;
	line: number;
	character: number;
	length: number;
	range: vscode.Range;
}

/**
 * A logical command: one or more physical lines joined with the backslash
 * continuation character.
 */
export interface LogicalLine {
	tokens: Token[];
	startLine: number;
	endLine: number;
}

/**
 * Parse a document into logical commands, applying the suanPan lexing rules:
 *
 *  - a line whose first non-space character is `#` is a full-line comment;
 *  - everything after the first `!` on a line is an inline comment;
 *  - commas and tabs are separators;
 *  - a trailing `\` joins the line with the next one.
 *
 * The parser is deliberately forgiving: it never throws on malformed input and
 * simply yields the tokens it can find.
 */
export function parseDocument(document: vscode.TextDocument): LogicalLine[] {
	const logical: LogicalLine[] = [];
	let current: Token[] | undefined;
	let startLine = 0;

	for (let line = 0; line < document.lineCount; line++) {
		const raw = document.lineAt(line).text;

		if (raw.trimStart().startsWith('#')) continue;

		let content = raw;
		const bang = content.indexOf('!');
		if (bang >= 0) content = content.slice(0, bang);

		let continuing = false;
		const rightTrimmed = content.replace(/\s+$/, '');
		if (rightTrimmed.endsWith('\\')) {
			continuing = true;
			content = rightTrimmed.replace(/\\+$/, '');
		}

		if (!current) {
			current = [];
			startLine = line;
		}

		// commas and tabs act as separators
		content = content.replace(/[,\t]/g, ' ');

		const re = /\S+/g;
		let match: RegExpExecArray | null;
		while ((match = re.exec(content)) !== null) {
			const character = match.index;
			const length = match[0].length;
			current.push({
				text: match[0],
				line,
				character,
				length,
				range: new vscode.Range(line, character, line, character + length)
			});
		}

		if (!continuing) {
			if (current.length > 0) {
				logical.push({ tokens: current, startLine, endLine: line });
			}
			current = undefined;
		}
	}

	if (current && current.length > 0) {
		logical.push({ tokens: current, startLine, endLine: current[current.length - 1].line });
	}

	return logical;
}

/**
 * Return the deepest token containing `position`, if any.
 */
export function tokenAt(lines: LogicalLine[], position: vscode.Position): Token | undefined {
	for (const line of lines) {
		if (position.line < line.startLine || position.line > line.endLine) continue;
		for (const token of line.tokens) {
			if (token.range.contains(position)) return token;
		}
	}
	return undefined;
}

/** Return the logical line that covers `position`, if any. */
export function lineAt(lines: LogicalLine[], position: vscode.Position): LogicalLine | undefined {
	return lines.find(line => position.line >= line.startLine && position.line <= line.endLine);
}

/** Index of `token` within its logical line, or -1. */
export function tokenIndex(line: LogicalLine, token: Token): number {
	return line.tokens.indexOf(token);
}
