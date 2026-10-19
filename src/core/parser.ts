/**
 * A faithful, line based parser for suanPan model files.
 *
 * The parser mirrors `normalise_command()` from `Toolbox/command.cpp`:
 *  - comment lines start with `#`,
 *  - inline comments start with `!`,
 *  - commas and tabs are delimiters,
 *  - a trailing backslash joins the next line.
 *
 * It is intentionally tolerant. It does not validate argument types; it only
 * produces enough structure for editor features.
 */

export interface SourceToken {
    value: string;
    line: number;
    start: number;
    end: number;
    endLine: number;
}

export interface Statement {
    /** Normalised command text (single spaces between tokens). */
    text: string;
    tokens: SourceToken[];
    /** First line of the statement (0 based). */
    line: number;
    /** Last line of the statement (0 based). */
    endLine: number;
    /** Lower case first token. */
    verb: string;
}

export interface ParsedDocument {
    lines: string[];
    statements: Statement[];
    /** Start line of a continuation that reaches the end of the file. */
    danglingContinuation?: number;
    /** Comment lines, used for folding ranges. */
    commentLines: number[];
}

interface CharPosition {
    line: number;
    column: number;
}

function tokenize(buffer: string, positions: CharPosition[], startLine: number): Statement | undefined {
    const tokens: SourceToken[] = [];
    const pattern = /\S+/g;
    let match: RegExpExecArray | null;
    let endLine = startLine;
    while ((match = pattern.exec(buffer)) !== null) {
        const first = positions[match.index];
        const last = positions[match.index + match[0].length - 1];
        if (!first || !last) continue;
        tokens.push({
            value: match[0],
            line: first.line,
            start: first.column,
            end: last.column + 1,
            endLine: last.line,
        });
        endLine = last.line;
    }
    if (tokens.length === 0) return undefined;
    return {
        text: tokens.map(token => token.value).join(' '),
        tokens,
        line: tokens[0].line,
        endLine,
        verb: tokens[0].value.toLowerCase(),
    };
}

/** Parse a suanPan model document. */
export function parseDocument(text: string): ParsedDocument {
    const lines = text.split(/\r\n|\n|\r/);
    const statements: Statement[] = [];
    const commentLines: number[] = [];

    let buffer = '';
    let positions: CharPosition[] = [];
    let startLine = -1;

    const flush = () => {
        const statement = tokenize(buffer, positions, startLine);
        if (statement) statements.push(statement);
        buffer = '';
        positions = [];
        startLine = -1;
    };

    for (let line = 0; line < lines.length; line++) {
        const raw = lines[line];

        if (/^\s*#/.test(raw)) {
            commentLines.push(line);
            continue;
        }

        const bang = raw.indexOf('!');
        let code = bang >= 0 ? raw.slice(0, bang) : raw;
        // Commas and tabs are delimiters. Replacing a single character keeps
        // the column mapping intact.
        code = code.replace(/[,\t\r]/g, ' ');

        // `sanitize_command(command_line, ' ')` trims trailing whitespace.
        code = code.replace(/\s+$/, '');
        if (code.trim() === '') continue;

        let continuation = false;
        if (code.endsWith('\\')) {
            continuation = true;
            code = code.replace(/\\+$/, '');
        }

        if (startLine < 0) startLine = line;
        for (let column = 0; column < code.length; column++) {
            buffer += code[column];
            positions.push({ line, column });
        }

        if (!continuation) flush();
    }

    if (buffer.trim() !== '') {
        const statement = tokenize(buffer, positions, startLine);
        if (statement) statements.push(statement);
        return { lines, statements, commentLines, danglingContinuation: startLine };
    }

    return { lines, statements, commentLines };
}

/** Token at a given document position. */
export function tokenAt(statement: Statement, line: number, character: number): SourceToken | undefined {
    return statement.tokens.find(token => {
        if (token.line === line && token.endLine === line) return character >= token.start && character < token.end;
        if (token.line === line) return character >= token.start;
        if (token.endLine === line) return character < token.end;
        return line > token.line && line < token.endLine;
    });
}

/** Index of a token inside its statement. */
export function tokenIndex(statement: Statement, token: SourceToken): number {
    return statement.tokens.indexOf(token);
}

/** Statement covering a line, if any. */
export function statementAt(parsed: ParsedDocument, line: number): Statement | undefined {
    return parsed.statements.find(statement => line >= statement.line && line <= statement.endLine);
}
