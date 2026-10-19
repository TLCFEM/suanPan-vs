import { CommandDatabase, TYPED_CATEGORIES } from './database';
import { ParsedDocument, Statement, SourceToken } from './parser';

export interface SymbolInfo {
    category: string;
    tag: number;
    typeName?: string;
    statement: Statement;
    token: SourceToken;
}

export interface Model {
    parsed: ParsedDocument;
    symbols: Map<string, Map<number, SymbolInfo>>;
    /** All definitions in document order. */
    definitions: SymbolInfo[];
    variables: Map<string, { name: string; statement: Statement; token: SourceToken }>;
    domains: Statement[];
}

export interface Reference {
    category: string;
    tag: number;
    token: SourceToken;
}

const OBJECT_TYPES: Record<string, string> = {
    node: 'node',
    element: 'element',
    material: 'material',
    section: 'section',
    constraint: 'constraint',
    load: 'load',
    amplitude: 'amplitude',
    expression: 'expression',
    group: 'group',
    step: 'step',
    solver: 'solver',
    integrator: 'integrator',
    converger: 'converger',
    criterion: 'criterion',
    recorder: 'recorder',
    modifier: 'modifier',
    interaction: 'interaction',
};

const OBJECT_COMMANDS = new Set(['peek', 'delete', 'erase', 'remove', 'enable', 'disable', 'mute', 'protect', 'suspend']);

function integerValue(token: SourceToken | undefined): number | undefined {
    if (!token || !/^\d+$/.test(token.value)) return undefined;
    const value = Number(token.value);
    return Number.isSafeInteger(value) ? value : undefined;
}

/** Find the token index that holds the object tag, if the statement defines one. */
export function tagTokenIndex(statement: Statement, database: CommandDatabase): number | undefined {
    const command = database.findCommand(statement.verb);
    if (!command) return undefined;

    if (['node', 'domain', 'mass', 'recorder', 'hdf5recorder', 'plainrecorder'].includes(statement.verb)) {
        return 1;
    }

    if (command.name === command.category && command.types?.length && TYPED_CATEGORIES.has(command.category ?? '')) {
        const numeric = (index: number) => !!statement.tokens[index] && /^\d+$/.test(statement.tokens[index].value);
        // `section NZ2D 1000WB215 5 ...` inserts a designation before the tag.
        if (command.category === 'section') {
            if (numeric(2)) return 2;
            if (!numeric(2) && numeric(3)) return 3;
            return undefined;
        }
        return numeric(2) ? 2 : undefined;
    }

    return undefined;
}

export function buildModel(parsed: ParsedDocument, database: CommandDatabase): Model {
    const symbols = new Map<string, Map<number, SymbolInfo>>();
    const definitions: SymbolInfo[] = [];
    const variables = new Map<string, { name: string; statement: Statement; token: SourceToken }>();
    const domains: Statement[] = [];

    const add = (symbol: SymbolInfo) => {
        const bucket = symbols.get(symbol.category) ?? new Map<number, SymbolInfo>();
        // First definition wins, matching the interpreter where duplicate tags
        // are rejected but the original object remains accessible.
        if (!bucket.has(symbol.tag)) bucket.set(symbol.tag, symbol);
        symbols.set(symbol.category, bucket);
        definitions.push(symbol);
    };

    for (const statement of parsed.statements) {
        if (statement.verb === 'domain') domains.push(statement);

        if (statement.verb === 'var' || statement.verb === 'variable') {
            const name = statement.tokens[1];
            if (name) {
                variables.set(name.value.toLowerCase(), { name: name.value, statement, token: name });
            }
            continue;
        }

        const command = database.findCommand(statement.verb);
        if (!command?.category) continue;

        const tagIndex = tagTokenIndex(statement, database);
        if (tagIndex === undefined) continue;

        const token = statement.tokens[tagIndex];
        const tag = integerValue(token);
        if (tag === undefined || !token) continue;

        const typeIndex = database.typeTokenIndex(statement.verb);
        const typeName = typeIndex === undefined ? undefined : statement.tokens[typeIndex]?.value;

        add({ category: command.category, tag, typeName, statement, token });
    }

    return { parsed, symbols, definitions, variables, domains };
}

export function findSymbol(model: Model, category: string, tag: number): SymbolInfo | undefined {
    return model.symbols.get(category)?.get(tag);
}

/** Definitions of a category, sorted by tag. */
export function symbolsOf(model: Model, category: string): SymbolInfo[] {
    return [...(model.symbols.get(category)?.values() ?? [])].sort((a, b) => a.tag - b.tag);
}

/**
 * Resolve a token to the object it refers to.
 *
 * Argument documentation (`material tag`, `node i`, ...) is used for ordinary
 * commands. Object management commands (`peek node 1`) are handled explicitly.
 */
export function referenceAt(
    statement: Statement,
    index: number,
    database: CommandDatabase
): Reference | undefined {
    const token = statement.tokens[index];
    const tag = integerValue(token);
    if (!token || tag === undefined) return undefined;

    if (OBJECT_COMMANDS.has(statement.verb) && index >= 2) {
        const category = OBJECT_TYPES[statement.tokens[1]?.value.toLowerCase() ?? ''];
        if (category) return { category, tag, token };
        return undefined;
    }

    const argument = database.argumentFor(
        statement.verb,
        statement.tokens.map(item => item.value),
        index
    );
    if (!argument) return undefined;

    const description = argument.description.toLowerCase();
    const mapping: Array<[RegExp, string]> = [
        [/\bmaterial tag\b/, 'material'],
        [/\bsection tag\b/, 'section'],
        [/\bnode i\b|\bnode j\b|\bnode tag\b|\bnodes?\b/, 'node'],
        [/\belement tag\b|\belements?\b/, 'element'],
        [/\bamplitude tag\b/, 'amplitude'],
        [/\bgroup tag\b|\bgroup\b/, 'group'],
        [/\bstep tag\b/, 'step'],
        [/\bsolver tag\b/, 'solver'],
        [/\bintegrator tag\b/, 'integrator'],
        [/\bconverger tag\b/, 'converger'],
        [/\bcriterion tag\b/, 'criterion'],
    ];
    for (const [pattern, category] of mapping) {
        if (pattern.test(description)) return { category, tag, token };
    }

    return undefined;
}
