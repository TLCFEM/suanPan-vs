import * as fs from 'fs';
import * as path from 'path';

import { parseSnippetBody, RANGE_MARKER, SnippetEntry, SnippetArg } from './snippets';

export interface TypeInfo {
    name: string;
    aliases?: string[];
    summary?: string;
    /** C++ factory expression from the unified ``TokenRegistry`` dispatch table. */
    factory?: string;
}

export interface CommandInfo {
    name: string;
    aliases: string[];
    category?: string;
    summary?: string;
    types?: TypeInfo[];
}

interface DatabaseFile {
    version: string;
    commands: CommandInfo[];
}

interface RawSnippet {
    prefix?: string;
    description?: string;
    body?: string[];
}

/** Categories whose `command <Type> <tag> ...` layout has a type keyword. */
export const TYPED_CATEGORIES = new Set([
    'amplitude',
    'constraint',
    'converger',
    'criterion',
    'element',
    'expression',
    'group',
    'integrator',
    'interaction',
    'load',
    'material',
    'modifier',
    'orientation',
    'section',
    'solver',
    'step',
]);

const SNIPPET_FILES = ['snippets.json', 'nz_sections.json', 'eu_sections.json', 'us_sections.json'];

const PLACEHOLDER = /\$\{\d+/;

/**
 * Align snippet argument positions with the tokens of a concrete statement.
 *
 * A snippet may describe the same object in a longer form: the `nodegroup`
 * snippet starts with `group nodegroup ...`, and `embed2d` reuses the
 * `constraint Embed2D ...` snippet.  Match the literal words of the template
 * against the statement and shift the argument indices accordingly.
 */
function alignSnippet(entry: SnippetEntry, tokens: string[], equivalents: Set<string> = new Set()): SnippetEntry {
    const template = entry.templates[0];
    if (!template || tokens.length === 0) return entry;

    const words = template.trim().split(/\s+/);
    const literals = words
        .map((word, index) => ({ word: word.toLowerCase(), index }))
        .filter(({ word }) => !PLACEHOLDER.test(word) && !RANGE_MARKER.test(word));
    if (literals.length === 0) return entry;

    let best: { offset: number; score: number } | undefined;
    for (let offset = -words.length; offset <= tokens.length; offset++) {
        let score = 0;
        let valid = true;
        for (const literal of literals) {
            const position = offset + literal.index;
            if (position < 0 || position >= tokens.length) continue;
            const token = tokens[position].toLowerCase();
            const equivalent = equivalents.has(token) && equivalents.has(literal.word);
            if (token !== literal.word && !equivalent) {
                valid = false;
                break;
            }
            score++;
        }
        if (!valid || score === 0) continue;
        if (!best || score > best.score || (score === best.score && offset === 0)) {
            best = { offset, score };
        }
    }
    if (!best || best.offset === 0) return entry;

    const offset = best.offset;
    const templates =
        offset < 0 ? entry.templates.map(line => line.trim().split(/\s+/).slice(-offset).join(' ')) : entry.templates;
    const args = entry.args.flatMap(argument => {
        if (argument.tokenIndex < 0) return [argument];
        const tokenIndex = argument.tokenIndex + offset;
        return tokenIndex >= 1 ? [{ ...argument, tokenIndex }] : [];
    });
    return { ...entry, templates, args };
}

export class CommandDatabase {
    readonly version: string;

    private readonly commands = new Map<string, CommandInfo>();
    private readonly all: CommandInfo[] = [];

    private readonly commandSnippets = new Map<string, SnippetEntry>();
    private readonly snippetsByCommandType = new Map<string, SnippetEntry>();
    private readonly snippetsByTrigger = new Map<string, SnippetEntry[]>();
    private readonly designations = new Map<string, SnippetEntry[]>();

    private constructor(version: string) {
        this.version = version;
    }

    /** Load the generated command database and the bundled snippets. */
    static load(extensionRoot: string): CommandDatabase {
        const database = JSON.parse(
            fs.readFileSync(path.join(extensionRoot, 'data', 'database.json'), 'utf8')
        ) as DatabaseFile;

        const result = new CommandDatabase(database.version);

        for (const command of database.commands) {
            result.all.push(command);
            result.commands.set(command.name.toLowerCase(), command);
            for (const alias of command.aliases) result.commands.set(alias.toLowerCase(), command);
        }
        result.all.sort((a, b) => a.name.localeCompare(b.name));

        for (const file of SNIPPET_FILES) {
            const location = path.join(extensionRoot, 'syntaxes', file);
            if (!fs.existsSync(location)) continue;
            const snippets = JSON.parse(fs.readFileSync(location, 'utf8')) as Record<string, RawSnippet>;
            for (const raw of Object.values(snippets)) result.addSnippet(raw);
        }

        return result;
    }

    private addSnippet(raw: RawSnippet): void {
        if (!raw.body || raw.body.length === 0) return;
        const { templates, args } = parseSnippetBody(raw.body);
        if (templates.length === 0) return;

        const words = templates[0].trim().split(/\s+/);
        const verb = words[0].toLowerCase();
        const isPlaceholder = (word: string | undefined) => !!word && /^\$\{\d+:/.test(word);

        const entry: SnippetEntry = {
            prefix: raw.prefix ?? '',
            summary: raw.description ?? '',
            verb,
            templates,
            args,
        };

        if (!isPlaceholder(words[1])) entry.typeName = words[1];

        // `section NZ2D 1000WB215 ...` entries describe a named designation.
        const isDesignation =
            verb === 'section' && words.length > 2 && !isPlaceholder(words[1]) && !isPlaceholder(words[2]);

        // A first-level command template (`node`, `recorder`, ...).
        if (!entry.typeName && !this.commandSnippets.has(verb)) this.commandSnippets.set(verb, entry);

        if (entry.typeName && !isDesignation) {
            const key = `${verb}:${entry.typeName.toLowerCase()}`;
            if (!this.snippetsByCommandType.has(key)) this.snippetsByCommandType.set(key, entry);
        }

        const trigger = entry.prefix.toLowerCase();
        if (trigger) {
            const bucket = this.snippetsByTrigger.get(trigger) ?? [];
            bucket.push(entry);
            this.snippetsByTrigger.set(trigger, bucket);
        }

        if (isDesignation) {
            const container = words[1].toLowerCase();
            const bucket = this.designations.get(container) ?? [];
            bucket.push(entry);
            this.designations.set(container, bucket);
        }
    }

    /** Find a command by name or alias. */
    findCommand(name: string): CommandInfo | undefined {
        return this.commands.get(name.toLowerCase());
    }

    /** All canonical commands, sorted by name. */
    listCommands(): readonly CommandInfo[] {
        return this.all;
    }

    /** All spellings (name + aliases) that can start a command. */
    commandNames(): string[] {
        const names = new Set<string>();
        for (const command of this.all) {
            names.add(command.name);
            for (const alias of command.aliases) names.add(alias);
        }
        return [...names].sort((a, b) => a.localeCompare(b));
    }

    /** All type keywords accepted by a command (aliases included). */
    typesFor(commandName: string): TypeInfo[] {
        const command = this.findCommand(commandName);
        if (!command) return [];
        if (command.types) return command.types;
        if (command.category === 'recorder') return this.findCommand('recorder')?.types ?? [];
        return [];
    }

    /** Resolve a type keyword for the given command. */
    findType(commandName: string, token: string): TypeInfo | undefined {
        const command = this.findCommand(commandName);
        if (!command) return undefined;
        // `hdf5recorder`/`plainrecorder` share the object types of `recorder`.
        const types = command.types ?? (command.category === 'recorder' ? this.findCommand('recorder')?.types : undefined);
        if (!types) return undefined;
        const lower = token.toLowerCase();
        return types.find(
            type => type.name.toLowerCase() === lower || type.aliases?.some(alias => alias.toLowerCase() === lower)
        );
    }

    /** The token index at which the type keyword is expected. */
    typeTokenIndex(commandName: string): number | undefined {
        const command = this.findCommand(commandName);
        if (!command) return undefined;
        if (command.name === 'recorder') return 3;
        if (command.name === 'hdf5recorder' || command.name === 'plainrecorder') return 2;
        if (!command.types?.length) return undefined;
        return 1;
    }

    /** Find the snippet template describing a complete statement. */
    snippetFor(verb: string, tokens: string[]): SnippetEntry | undefined {
        const lowerVerb = verb.toLowerCase();
        const command = this.findCommand(lowerVerb);
        const type = tokens.length > 1 ? this.findType(lowerVerb, tokens[1]) : undefined;
        const spellings = [tokens[1], type?.name, ...(type?.aliases ?? [])].filter(
            (name): name is string => !!name
        );
        const unique = spellings.filter(
            (name, index) => spellings.findIndex(other => other.toLowerCase() === name.toLowerCase()) === index
        );
        const equivalents = new Set(unique.map(name => name.toLowerCase()));

        if (lowerVerb === 'section' && tokens.length > 2) {
            for (const candidate of this.snippetsByTrigger.get(tokens[2].toLowerCase()) ?? []) {
                if (candidate.verb === 'section' && candidate.typeName?.toLowerCase() === tokens[1].toLowerCase()) {
                    return alignSnippet(candidate, tokens, equivalents);
                }
            }
        }

        // Recorder types such as `recorder 1 hdf5 Modal U1` place the type
        // keyword after the optional format word. Reuse a type-specific
        // snippet (e.g. the Modal influence directions) when one is available.
        const recorderTypeIndex =
            lowerVerb === 'recorder' ? 3 : lowerVerb === 'hdf5recorder' || lowerVerb === 'plainrecorder' ? 2 : -1;
        if (recorderTypeIndex >= 0 && tokens.length > recorderTypeIndex) {
            for (const candidate of this.snippetsByTrigger.get(tokens[recorderTypeIndex].toLowerCase()) ?? []) {
                if (candidate.verb === 'recorder') return alignSnippet(candidate, tokens, equivalents);
            }
        }

        for (const name of unique) {
            const byType = this.snippetsByCommandType.get(`${lowerVerb}:${name.toLowerCase()}`);
            if (byType) return alignSnippet(byType, tokens, equivalents);
        }

        // Types such as `load Cload` are normally written through their alias
        // command (`cload`). Reuse the matching command snippet when the
        // category agrees.
        if (command?.category && tokens.length > 1) {
            for (const name of unique) {
                for (const candidate of this.snippetsByTrigger.get(name.toLowerCase()) ?? []) {
                    const candidateCommand = this.findCommand(candidate.verb);
                    if (candidateCommand?.category === command.category) {
                        return alignSnippet(candidate, tokens, equivalents);
                    }
                }
            }
        }

        // Shorthand commands (`nodegroup`, `embed2d`, ...) reuse the snippet of
        // the canonical `group nodegroup` / `constraint Embed2D` form.
        for (const candidate of this.snippetsByTrigger.get(lowerVerb) ?? []) {
            const candidateCommand = this.findCommand(candidate.verb);
            if (
                candidate.verb === lowerVerb ||
                (command?.category && candidateCommand?.category === command.category)
            ) {
                return alignSnippet(candidate, tokens, equivalents);
            }
        }

        const fallback = this.commandSnippets.get(lowerVerb);
        return fallback ? alignSnippet(fallback, tokens, equivalents) : undefined;
    }

    /** Named section designations for a container such as `NZ2D`. */
    designationsFor(container: string): SnippetEntry[] {
        return this.designations.get(container.toLowerCase()) ?? [];
    }

    /** All snippets whose template starts with the given verb. */
    snippetsFor(verb: string): SnippetEntry[] {
        const result: SnippetEntry[] = [];
        for (const entries of this.snippetsByTrigger.values()) {
            for (const entry of entries) if (entry.verb === verb.toLowerCase()) result.push(entry);
        }
        return result;
    }

    /** Argument metadata for a token position in a statement. */
    argumentFor(verb: string, tokens: string[], tokenIndex: number): SnippetArg | undefined {
        const snippet = this.snippetFor(verb, tokens);
        if (!snippet) return undefined;
        const exact = snippet.args.find(arg => arg.tokenIndex === tokenIndex);
        if (exact) return exact;
        // Ranged arguments (`(2...9)`, `[5...]`) cover several tokens.
        return snippet.args.find(
            arg => arg.tokenIndex >= 0 && tokenIndex > arg.tokenIndex && tokenIndex < arg.tokenIndex + arg.count
        );
    }
}
